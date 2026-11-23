"""Gera os dicionários do ano que acompanham a tabela de contagens.

Entradas: entrega/<ano>/contagens_<ano>.csv.gz (contar_celulas.py), tratados/<ano>/municipios.csv, tratados/cbo/familias_cbo.csv
          e os manifestos dos downloads.
Saídas em entrega/<ano>/:
- municipios_<ano>.csv: os municípios da DTB do ano, inclusive os sem vínculos, com os vínculos do estoque de cada um;
- familias_cbo_<ano>.csv: as famílias declaradas na RAIS do ano, que formam a estrutura ocupacional do ano, com o título
  da CBO, os vínculos no Brasil, se o código identifica uma família, se está na tabela atual da CBO e se é nova no ano;
- categorias.csv: os códigos de cada variável, com os grupos usados nos recortes e os anos de estudo de cada escolaridade;
- colunas.csv: o que é cada coluna da tabela de contagens e dos dicionários;
- manifesto_<ano>.csv: os arquivos baixados (endereço, tamanho, data na fonte, data do download e md5).

Uso: python 3_contagem/gerar_dicionarios.py 2025
"""
import csv
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import ano_do_argumento, log, pasta  # noqa: E402

# Anos de estudo atribuídos a cada categoria de escolaridade (escala da nota metodológica, Quadro 7).
ESCOLARIDADE = [('1', 'Analfabeto', 0), ('2', 'Até o 5º ano incompleto', 2), ('3', '5º ano completo', 5),
                ('4', 'Do 6º ao 9º ano incompleto', 6.5), ('5', 'Fundamental completo', 9), ('6', 'Médio incompleto', 10),
                ('7', 'Médio completo', 12), ('8', 'Superior incompleto', 13.5), ('9', 'Superior completo', 16),
                ('10', 'Mestrado completo', 18), ('11', 'Doutorado completo', 22)]
# (variável, código, rótulo, grupo usado nos recortes do DEP)
CATEGORIAS = [
    ('sexo', '1', 'Masculino', 'Masculino'), ('sexo', '2', 'Feminino', 'Feminino'), ('sexo', '', 'Não classificado', 'Não classificado'),
    ('faixa_etaria', '2', '15 a 17 anos', '15 a 17'),   # a faixa 1 (10 a 14 anos) fica fora do universo
    ('faixa_etaria', '3', '18 a 24 anos', '18 a 24'), ('faixa_etaria', '4', '25 a 29 anos', '25 a 29'),
    ('faixa_etaria', '5', '30 a 39 anos', '30 a 39'), ('faixa_etaria', '6', '40 a 49 anos', '40 a 49'),
    ('faixa_etaria', '7', '50 a 64 anos', '50 a 64'), ('faixa_etaria', '8', '65 anos ou mais', '65 ou mais'),
    ('faixa_etaria', '99', 'Não classificada', 'Não classificada'),
    ('raca_cor', '1', 'Indígena', 'Indígenas e amarelas'), ('raca_cor', '6', 'Amarela', 'Indígenas e amarelas'),
    ('raca_cor', '2', 'Branca', 'Brancas'), ('raca_cor', '4', 'Preta', 'Pretas e pardas'), ('raca_cor', '8', 'Parda', 'Pretas e pardas'),
    ('raca_cor', '9', 'Não identificada', 'Não declarada ou ignorada'), ('raca_cor', '99', 'Ignorada', 'Não declarada ou ignorada'),
    ('setor', '1', 'Indústria (subsetores IBGE 1 a 14)', 'Indústria'), ('setor', '2', 'Construção civil (subsetor 15)', 'Construção'),
    ('setor', '3', 'Comércio (subsetores 16 e 17)', 'Comércio'),
    ('setor', '4', 'Serviços e administração pública (subsetores 18 a 24)', 'Serviços e administração pública'),
    ('setor', '5', 'Agropecuária (subsetor 25)', 'Agropecuária'), ('setor', '', 'Não informado', 'Não informado'),
]
COLUNAS = [
    ('contagens', 'ano', 'número', 'Ano-base da RAIS'),
    ('contagens', 'id_municipio', 'texto, 6 dígitos', 'Município do estabelecimento (código do IBGE sem o dígito verificador). '
     'Vazio quando o código não está na DTB do ano: o vínculo entra na referência nacional, mas não em municípios'),
    ('contagens', 'cbo_familia', 'texto, 4 dígitos', 'Família da CBO (4 primeiros dígitos da ocupação). Vazio quando o código não é '
     'numérico; 0000 e 9999 não identificam família. Ver familias_cbo_<ano>.csv'),
    ('contagens', 'escolaridade', 'número', 'Escolaridade (1 a 11; ver categorias.csv, com os anos de estudo). Outros valores ou vazio: '
     'escolaridade inválida, fora do cálculo'),
    ('contagens', 'sexo', 'texto', 'Código da RAIS (ver categorias.csv)'),
    ('contagens', 'faixa_etaria', 'texto', 'Código da RAIS (ver categorias.csv)'),
    ('contagens', 'raca_cor', 'texto', 'Código da RAIS (ver categorias.csv, com os grupos do DEP)'),
    ('contagens', 'setor', 'texto', 'Setor agrupado a partir do subsetor do IBGE (ver categorias.csv); vazio = não informado'),
    ('contagens', 'vinculos', 'número', 'Vínculos do universo do DEP com essa combinação: ativos em 31/12, sem a marcação de '
     'abandono e fora da faixa etária de 10 a 14 anos'),
    ('formato', 'contagens_<ano>.csv.gz', '', 'CSV em UTF-8 compactado com gzip, separado por vírgula, com cabeçalho; códigos lidos como '
     'texto para manter os zeros à esquerda; uma linha por combinação; a soma de vinculos é o estoque divulgado pelo MTE '
     'menos a faixa de 10 a 14 anos (ver universo_<ano>.csv)'),
    ('municipios', 'id_municipio, id_municipio_ibge', 'texto', 'Código com 6 e com 7 dígitos'),
    ('municipios', 'municipio, uf, sigla_uf, nome_uf', 'texto', 'Nome do município e a UF, segundo a DTB do ano'),
    ('municipios', 'vinculos', 'número', 'Vínculos do universo no município (todas as linhas da tabela de contagens do município)'),
    ('universo', 'estoque_mte, faixa_10_a_14, universo_dep', 'número', 'Estoque divulgado pelo MTE, vínculos da faixa de 10 a 14 '
     'anos retirados e total da tabela de contagens'),
    ('familias_cbo', 'cbo_familia, titulo', 'texto', 'Código e título da família (título da tabela atual da CBO)'),
    ('familias_cbo', 'vinculos_brasil', 'número', 'Vínculos do universo declarados na família no ano, no Brasil'),
    ('familias_cbo', 'identifica_familia', 'sim/não', 'não para 0000 e 9999, que ficam fora do cálculo'),
    ('familias_cbo', 'na_tabela_cbo', 'sim/não', 'Se a família está na tabela atual da CBO baixada do MTE'),
    ('familias_cbo', 'nova_no_ano', 'sim/não/vazio', 'sim se a família não foi declarada no ano anterior; vazio sem o dicionário do ano anterior'),
]


# Grava uma tabela em CSV (UTF-8, separada por vírgula).
def gravar(caminho, campos, linhas):
    with open(caminho, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(campos)
        w.writerows(linhas)


# Lê um CSV como lista de dicionários.
def ler(caminho):
    with open(caminho, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


if __name__ == '__main__':
    ano = ano_do_argumento()
    entrega = pasta('entrega', ano)
    contagens = (entrega / f'contagens_{ano}.csv.gz').as_posix()
    con = duckdb.connect()
    # a tabela de contagens do ano, com os códigos lidos como texto para manter os zeros à esquerda
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_csv('{contagens}', types={{'id_municipio': 'VARCHAR', 'cbo_familia': 'VARCHAR'}})")

    # municípios da DTB do ano, com os vínculos de cada um (zero quando não há vínculos)
    por_mun = dict(con.execute('SELECT id_municipio, SUM(vinculos) FROM c WHERE id_municipio IS NOT NULL GROUP BY 1').fetchall())
    municipios = ler(pasta('tratados', ano) / 'municipios.csv')
    gravar(entrega / f'municipios_{ano}.csv', list(municipios[0]) + ['vinculos'],
           [list(m.values()) + [por_mun.get(m['id_municipio'], 0)] for m in municipios])

    # famílias declaradas no ano: a estrutura ocupacional do ano
    titulos = {l['cbo_familia']: l['titulo'] for l in ler(pasta('tratados', 'cbo') / 'familias_cbo.csv')}
    # famílias do ano anterior, se o dicionário dele existir, para marcar as famílias novas no ano
    anterior = pasta('entrega', ano - 1) / f'familias_cbo_{ano - 1}.csv'
    antes = {l['cbo_familia'] for l in ler(anterior)} if anterior.exists() else None
    # cada família declarada no ano, com os vínculos no Brasil
    familias = con.execute('SELECT cbo_familia, SUM(vinculos) FROM c WHERE cbo_familia IS NOT NULL GROUP BY 1 ORDER BY 1').fetchall()
    sim = lambda x: 'sim' if x else 'não'
    gravar(entrega / f'familias_cbo_{ano}.csv',
           ['cbo_familia', 'titulo', 'vinculos_brasil', 'identifica_familia', 'na_tabela_cbo', 'nova_no_ano'],
           [[f, titulos.get(f, ''), n, sim(f not in ('0000', '9999')), sim(f in titulos), '' if antes is None else sim(f not in antes)]
            for f, n in familias])

    # dicionários fixos: os códigos das variáveis e as colunas da tabela
    gravar(entrega / 'categorias.csv', ['variavel', 'codigo', 'rotulo', 'grupo_dep', 'anos_de_estudo'],
           [('escolaridade', c, r, r, a) for c, r, a in ESCOLARIDADE] + [(v, c, r, g, '') for v, c, r, g in CATEGORIAS])
    gravar(entrega / 'colunas.csv', ['arquivo', 'coluna', 'tipo', 'descricao'], COLUNAS)

    # junta os manifestos dos downloads (RAIS, DTB e CBO) num só arquivo da entrega
    manifestos = [pasta('brutos', ano) / 'manifesto.csv', pasta('brutos', 'cbo') / 'manifesto.csv']
    linhas = [l for m in manifestos for l in ler(m)]
    gravar(entrega / f'manifesto_{ano}.csv', list(linhas[0]), [list(l.values()) for l in linhas])
    log(f'{ano}: {len(municipios)} municípios, {len(familias)} famílias declaradas, dicionários em {entrega}')
