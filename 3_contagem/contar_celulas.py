"""Soma as contagens dos arquivos da RAIS de um ano e grava a tabela de contagens entregue à plataforma.

Entrada: tratados/<ano>/rais/*.parquet e conferencia.csv (2_tratamento/tratar_rais.py)
Saída:   entrega/<ano>/contagens_<ano>.csv.gz

A tabela tem uma linha por combinação de município, família da CBO, escolaridade, sexo, faixa etária, raça ou cor e
setor, com o número de vínculos. Linhas com zero vínculos não existem. Traz o universo do DEP: o estoque divulgado pelo
MTE (ativos em 31/12 sem a marcação de abandono) sem a faixa etária de 10 a 14 anos (código 1), que é trabalho infantil
e fica fora do indicador. Entram também os vínculos com escolaridade ou família inválida e os sem município: a
plataforma precisa deles para a referência nacional, para o Brasil e para a cobertura (ver colunas.csv e a nota).

Conferências (o processador para se alguma falhar):
1. o estoque lido nos arquivos (vínculos ativos em 31/12 sem a marcação de abandono) é igual ao divulgado pelo MTE para
   o ano, quando o número está em ESTOQUE_MTE;
2. a soma da tabela mais os vínculos da faixa de 10 a 14 anos é igual a esse estoque.
Grava também entrega/<ano>/universo_<ano>.csv com o estoque, os vínculos de 10 a 14 anos e o total da tabela.

Uso: python 3_contagem/contar_celulas.py 2025
"""
import csv
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import ano_do_argumento, log, pasta  # noqa: E402

# Estoque de empregos formais em 31/12 divulgado pelo MTE (Sumário executivo da RAIS, ano-base 2025, maio de 2026).
ESTOQUE_MTE = {2023: 55_316_614, 2024: 57_132_156, 2025: 59_970_945}
# Colunas que formam uma célula da tabela (além do ano).
COLUNAS = ['id_municipio', 'cbo_familia', 'escolaridade', 'sexo', 'faixa_etaria', 'raca_cor', 'setor']

if __name__ == '__main__':
    ano = ano_do_argumento()
    # estoque lido nos arquivos da RAIS, somado a partir da conferência do tratamento
    rais = pasta('tratados', ano, 'rais')
    with open(rais / 'conferencia.csv', encoding='utf-8') as f:
        lidos = sum(int(l['estoque']) for l in csv.DictReader(f))
    saida = pasta('entrega', ano) / f'contagens_{ano}.csv.gz'
    con = duckdb.connect()
    parquets = (rais / '*.parquet').as_posix()
    # 1. o estoque lido precisa ser exatamente o divulgado pelo MTE; se não for, o processador para
    oficial = ESTOQUE_MTE.get(ano)
    if oficial is None:
        log(f'Aviso: sem o estoque oficial de {ano} em ESTOQUE_MTE; confira {lidos:,} com o sumário executivo da RAIS'.replace(',', '.'))
    elif lidos != oficial:
        raise SystemExit(f'O estoque lido ({lidos}) difere do divulgado pelo MTE ({oficial})')
    # 2. vínculos da faixa de 10 a 14 anos (código 1), que saem do universo do DEP
    infantil = con.execute(f"SELECT COALESCE(SUM(vinculos), 0) FROM read_parquet('{parquets}') WHERE faixa_etaria = '1'").fetchone()[0]
    # 3. soma as células de todos os arquivos regionais, sem a faixa de 10 a 14 anos, e grava a tabela compactada
    # os mesmos códigos podem aparecer em arquivos regionais diferentes (por exemplo, sem município): soma-se tudo
    con.execute(f"""COPY (
        SELECT {ano} AS ano, {', '.join(COLUNAS)}, SUM(vinculos)::BIGINT AS vinculos
        FROM read_parquet('{parquets}') WHERE faixa_etaria IS DISTINCT FROM '1'   -- universo: sem 10 a 14 anos
        GROUP BY ALL ORDER BY ALL) TO '{saida.as_posix()}' (FORMAT CSV, HEADER, COMPRESSION GZIP)""")
    # 4. a tabela mais a faixa retirada precisa fechar com o estoque lido
    linhas, total = con.execute(f"SELECT COUNT(*), SUM(vinculos) FROM read_csv('{saida.as_posix()}', all_varchar=false)").fetchone()
    if total + infantil != lidos:
        raise SystemExit(f'A tabela ({total}) mais a faixa de 10 a 14 anos ({infantil}) não fecha com o estoque lido ({lidos})')
    # grava o estoque, a faixa retirada e o total da tabela
    with open(pasta('entrega', ano) / f'universo_{ano}.csv', 'w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([['estoque_mte', 'faixa_10_a_14', 'universo_dep'], [lidos, infantil, total]])
    log(f'{saida.name}: {linhas:,} linhas, {total:,} vínculos (estoque do MTE de {lidos:,} menos {infantil:,} de 10 a 14 anos)'.replace(',', '.'))
