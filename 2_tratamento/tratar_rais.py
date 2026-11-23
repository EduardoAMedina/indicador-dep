"""Trata os microdados de vínculos da RAIS de um ano: seleciona o estoque, harmoniza os códigos e conta os vínculos.

Entrada: brutos/<ano>/*.7z (1_download/baixar_rais.py) e tratados/<ano>/municipios.csv (tratar_municipios.py)
Saída:   tratados/<ano>/rais/<arquivo>.parquet, um por arquivo da RAIS, com a contagem de vínculos por combinação de
         município, família da CBO, escolaridade, sexo, faixa etária, raça ou cor e setor;
         tratados/<ano>/rais/conferencia.csv, com as linhas, os ativos e os abandonados lidos em cada arquivo.

Passos para cada arquivo (um por vez, para não ocupar o disco com todos descompactados):
1. Descompacta o .7z (um arquivo de texto, em Latin-1, separado por vírgula a partir de 2023).
2. Localiza as colunas pelo nome, e não pela posição (NOMES, abaixo).
3. Seleciona o estoque divulgado pelo MTE: vínculo ativo em 31/12 (indicador = 1) e sem a marcação de abandono (= 0).
   A faixa etária de 10 a 14 anos ainda fica aqui, para conferir o estoque com o do MTE; ela sai na contagem.
4. Harmoniza os códigos:
   - família da CBO: os 4 primeiros dígitos do código da ocupação, completado com zeros à esquerda até 6 dígitos;
     código não numérico fica vazio;
   - escolaridade: o código de 1 a 11, como número; outros valores ficam como vieram e saem do cálculo na plataforma;
   - sexo, faixa etária e raça ou cor: o código da RAIS sem zeros à esquerda; "{ñ class}" e negativos viram vazio
     (sexo) ou 99 (faixa etária e raça ou cor);
   - setor: o subsetor do IBGE agrupado em 5 setores (SETOR, abaixo); fora dos códigos 1 a 25, vazio (não informado);
   - município: o código de 6 dígitos, só se estiver na DTB do ano; fora dela, vazio. Esses vínculos continuam na
     tabela, porque entram na referência nacional, mas não recebem resultado municipal.
5. Conta os vínculos por combinação e confere que a soma é igual ao número de vínculos do estoque lidos no arquivo.

Uso: python 2_tratamento/tratar_rais.py 2025
"""
import csv
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import SETE_Z, ano_do_argumento, log, pasta  # noqa: E402

# Nome de cada coluna usada, depois de normalizado (sem acento, minúsculo, com _ no lugar de espaços e sinais).
NOMES = {'ativo': 'ind_vinculo_ativo_31_12_codigo', 'abandonado': 'ind_vinculo_abandonado_codigo',
         'ocupacao': 'cbo_2002_ocupacao_codigo', 'escolaridade': 'escolaridade_apos_2005_codigo', 'municipio': 'municipio_codigo',
         'sexo': 'sexo_codigo', 'faixa_etaria': 'faixa_etaria_codigo', 'raca_cor': 'raca_cor_codigo', 'subsetor': 'ibge_subsetor_codigo'}

def setor(coluna):
    """Subsetor do IBGE (1 a 25) → setor: 1 indústria, 2 construção, 3 comércio, 4 serviços e administração pública,
    5 agropecuária. Fora de 1 a 25 (98, 99 ou vazio): NULL, que é o setor "não informado"."""
    s = f'TRY_CAST(TRIM({coluna}) AS INTEGER)'
    return f"""CASE WHEN {s} BETWEEN 1 AND 14 THEN '1' WHEN {s} = 15 THEN '2' WHEN {s} IN (16, 17) THEN '3'
                    WHEN {s} BETWEEN 18 AND 24 THEN '4' WHEN {s} = 25 THEN '5' END"""


# Nome de coluna sem acento, minúsculo e com _ no lugar de espaços e sinais: 'Município - Código' vira 'municipio_codigo'.
def normalizar(nome):
    nome = unicodedata.normalize('NFKD', nome).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', nome).strip('_')


def codigo(coluna):
    """Código da RAIS como texto sem zeros à esquerda ('08' → '8'); vazio, negativo ou não numérico → NULL."""
    return f"CASE WHEN TRY_CAST(TRIM({coluna}) AS INTEGER) >= 0 THEN CAST(TRY_CAST(TRIM({coluna}) AS INTEGER) AS VARCHAR) END"


def tratar_arquivo(con, texto, saida):
    """Lê um arquivo de texto da RAIS e grava a contagem de vínculos do estoque por combinação. Devolve a conferência."""
    # 1. lê só o cabeçalho, para descobrir o separador e a posição de cada coluna
    with open(texto, encoding='latin-1') as f:
        cabecalho = f.readline().rstrip('\r\n')
    separador = ';' if cabecalho.count(';') > cabecalho.count(',') else ','
    nomes = [normalizar(c.strip('"')) for c in next(csv.reader([cabecalho], delimiter=separador))]
    # para se faltar alguma coluna usada (por exemplo, numa mudança de layout do MTE)
    faltam = [n for n in NOMES.values() if n not in nomes]
    if faltam:
        raise SystemExit(f'{texto.name}: colunas ausentes {faltam}')
    c = {chave: f'c{nomes.index(nome) + 1}' for chave, nome in NOMES.items()}   # coluna c1, c2, ... de cada variável
    # o DuckDB lê o arquivo inteiro como texto, com as colunas chamadas c1, c2, ...
    todas = ', '.join(f"'c{i + 1}'" for i in range(len(nomes)))
    con.execute(f"""CREATE OR REPLACE TEMP VIEW bruto AS SELECT * FROM read_csv('{texto.as_posix()}', delim='{separador}',
                    header=true, all_varchar=true, encoding='latin-1', quote='"', escape='"', names=[{todas}])""")
    # 2. estoque divulgado pelo MTE: vínculo ativo em 31/12 e sem a marcação de abandono
    estoque = f"TRIM({c['ativo']}) = '1' AND {codigo(c['abandonado'])} = '0'"
    # números para a conferência: linhas do arquivo, ativos em 31/12 e vínculos do estoque
    linhas, ativos, no_estoque = con.execute(f"""SELECT COUNT(*), COUNT(*) FILTER (WHERE TRIM({c['ativo']}) = '1'),
                                                 COUNT(*) FILTER (WHERE {estoque}) FROM bruto""").fetchone()
    # 3. harmoniza os códigos (regras no início deste arquivo), conta os vínculos do estoque por combinação
    #    e grava a contagem em Parquet; o código de município fora da DTB do ano fica vazio (LEFT JOIN)
    ocupacao = f"TRIM({c['ocupacao']})"
    con.execute(f"""COPY (
        SELECT m.id_municipio,
               CASE WHEN regexp_full_match({ocupacao}, '[0-9]{{1,6}}') THEN SUBSTR(LPAD({ocupacao}, 6, '0'), 1, 4) END AS cbo_familia,
               TRY_CAST(TRIM({c['escolaridade']}) AS INTEGER) AS escolaridade,
               {codigo(c['sexo'])} AS sexo,
               COALESCE({codigo(c['faixa_etaria'])}, '99') AS faixa_etaria,
               COALESCE({codigo(c['raca_cor'])}, '99') AS raca_cor,
               {setor(c['subsetor'])} AS setor,
               COUNT(*) AS vinculos
        FROM bruto LEFT JOIN municipios m ON TRIM({c['municipio']}) = m.id_municipio
        WHERE {estoque}
        GROUP BY ALL) TO '{saida.as_posix()}' (FORMAT PARQUET)""")
    # 4. confere que a contagem gravada soma exatamente o estoque lido no arquivo
    soma = con.execute(f"SELECT SUM(vinculos) FROM '{saida.as_posix()}'").fetchone()[0]
    if soma != no_estoque:
        raise SystemExit(f'{texto.name}: a contagem ({soma}) difere do estoque lido ({no_estoque})')
    return {'arquivo': texto.name, 'linhas': linhas, 'ativos_31_12': ativos, 'abandonados': ativos - no_estoque, 'estoque': no_estoque}


if __name__ == '__main__':
    ano = ano_do_argumento()
    brutos, saida = pasta('brutos', ano), pasta('tratados', ano, 'rais')
    con = duckdb.connect()
    # lista de municípios do ano, usada para reconhecer o código de município de cada vínculo
    con.execute(f"""CREATE TABLE municipios AS SELECT id_municipio FROM
                    read_csv('{(pasta('tratados', ano) / 'municipios.csv').as_posix()}', all_varchar=true)""")
    conferencia = []
    # um arquivo regional por vez: descompacta, trata, grava e apaga o texto descompactado
    for arquivo in sorted(brutos.glob('*.7z')):
        trabalho = pasta('tratados', ano, 'trabalho', arquivo.stem)
        log(f'{arquivo.name}: descompactando')
        subprocess.run([SETE_Z, 'x', '-y', f'-o{trabalho}', str(arquivo)], check=True, stdout=subprocess.DEVNULL)
        textos = [t for t in trabalho.iterdir() if t.is_file()]
        if len(textos) != 1:
            raise SystemExit(f'{arquivo.name}: esperado um arquivo de texto, encontrados {[t.name for t in textos]}')
        conferencia.append(tratar_arquivo(con, textos[0], saida / f'{arquivo.stem}.parquet'))
        shutil.rmtree(trabalho)                      # o texto descompactado tem vários GB e não é mais usado
        log(f"{arquivo.name}: {conferencia[-1]['estoque']:,} vínculos no estoque".replace(',', '.'))
    # grava a conferência de cada arquivo, usada na contagem para fechar com o estoque do MTE
    with open(saida / 'conferencia.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(conferencia[0]))
        w.writeheader()
        w.writerows(conferencia)
