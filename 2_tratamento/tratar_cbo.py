"""Converte a tabela de famílias da CBO para UTF-8, com o código da família como texto de 4 dígitos.

Entrada: brutos/cbo/cbo2002-familia.csv (1_download/baixar_cbo.py), em Windows-1252, separado por ponto e vírgula.
Saída:   tratados/cbo/familias_cbo.csv, com cbo_familia e titulo.

FAMILIAS_EXTRA traz famílias declaradas na RAIS que não estão na tabela publicada; hoje, só a 3227, que existe na
consulta da CBO no site do MTE mas falta no CSV de download.

Uso: python 2_tratamento/tratar_cbo.py
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import log, pasta  # noqa: E402

FAMILIAS_EXTRA = {'3227': 'Técnicos e profissionais em práticas integrativas e complementares (PICS)'}

if __name__ == '__main__':
    # lê a tabela do MTE (Windows-1252, separada por ponto e vírgula) e completa os códigos com zeros até 4 dígitos
    with open(pasta('brutos', 'cbo') / 'cbo2002-familia.csv', encoding='cp1252', newline='') as f:
        familias = {l['CODIGO'].strip().zfill(4): l['TITULO'].strip() for l in csv.DictReader(f, delimiter=';')}
    # acrescenta as famílias declaradas na RAIS que faltam na tabela publicada
    for codigo, titulo in FAMILIAS_EXTRA.items():
        familias.setdefault(codigo, titulo)
    # grava em UTF-8, em ordem de código
    saida = pasta('tratados', 'cbo') / 'familias_cbo.csv'
    with open(saida, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cbo_familia', 'titulo'])
        w.writerows(sorted(familias.items()))
    log(f'{len(familias)} famílias da CBO')
