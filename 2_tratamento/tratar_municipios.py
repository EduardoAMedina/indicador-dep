"""Monta a lista de municípios do ano a partir da DTB do IBGE.

Entrada: brutos/<ano>/DTB_<ano>.zip (1_download/baixar_municipios.py)
Saída:   tratados/<ano>/municipios.csv, com id_municipio (6 dígitos, como na RAIS), id_municipio_ibge (7 dígitos), municipio,
         uf (código de 2 dígitos), sigla_uf e nome_uf.

A RAIS identifica o município com os 6 primeiros dígitos do código do IBGE (sem o dígito verificador). A planilha de
municípios vem dentro do .zip em formato .ods, que é um .zip com um XML; ela é lida com a biblioteca padrão do Python.
O nome da planilha muda de um ano para outro, por isso ela é localizada pelo trecho "MUNICIP" no nome.

Uso: python 2_tratamento/tratar_municipios.py 2025
"""
import csv
import io
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import ano_do_argumento, log, pasta  # noqa: E402

SIGLAS = {'11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE',
          '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
          '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF'}
TAB = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
TXT = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'


def linhas_ods(conteudo):
    """Linhas da primeira planilha de um arquivo .ods, como listas de textos (células repetidas são expandidas)."""
    # o .ods é um .zip; a planilha está no arquivo XML content.xml
    raiz = ET.fromstring(zipfile.ZipFile(io.BytesIO(conteudo)).read('content.xml'))
    # percorre as linhas; uma célula pode valer por várias colunas seguidas (atributo number-columns-repeated)
    for linha in raiz.iter(f'{TAB}table-row'):
        celulas = []
        for c in linha.findall(f'{TAB}table-cell'):
            repete = min(int(c.get(f'{TAB}number-columns-repeated', '1')), 50)
            celulas += [''.join(t.text or '' for t in c.iter(f'{TXT}p')).strip()] * repete
        # linhas totalmente vazias são ignoradas
        if any(celulas):
            yield celulas


if __name__ == '__main__':
    ano = ano_do_argumento()
    # abre a DTB do ano e procura a planilha de municípios em .ods
    dtb = zipfile.ZipFile(pasta('brutos', ano) / f'DTB_{ano}.zip')
    planilha = [n for n in dtb.namelist() if re.search(r'MUNICIP.*\.ods$', n, re.I)]
    if len(planilha) != 1:
        raise SystemExit(f'Esperada uma planilha de municípios em .ods; encontradas: {planilha}')
    # lê todas as linhas da planilha
    linhas = list(linhas_ods(dtb.read(planilha[0])))
    # o cabeçalho é a linha com "Código Município Completo"; as linhas acima são o título do relatório
    i = next(i for i, l in enumerate(linhas) if 'Código Município Completo' in l)
    col = {nome: linhas[i].index(nome) for nome in ('UF', 'Nome_UF', 'Código Município Completo', 'Nome_Município')}
    # uma linha por município com código de 7 dígitos; a RAIS usa os 6 primeiros, sem o dígito verificador
    municipios = []
    for l in linhas[i + 1:]:
        codigo = l[col['Código Município Completo']]
        if re.fullmatch(r'\d{7}', codigo):
            municipios.append({'id_municipio': codigo[:6], 'id_municipio_ibge': codigo, 'municipio': l[col['Nome_Município']],
                               'uf': l[col['UF']], 'sigla_uf': SIGLAS[l[col['UF']]], 'nome_uf': l[col['Nome_UF']]})
    # confere que os códigos de 6 dígitos não se repetem, porque são eles que identificam o município na RAIS
    if len({m['id_municipio'] for m in municipios}) != len(municipios):
        raise SystemExit('Há códigos de 6 dígitos repetidos na DTB')
    # grava a lista em tratados/<ano>/municipios.csv, em ordem de código
    saida = pasta('tratados', ano) / 'municipios.csv'
    with open(saida, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(municipios[0]))
        w.writeheader()
        w.writerows(sorted(municipios, key=lambda m: m['id_municipio']))
    log(f'{ano}: {len(municipios)} municípios na DTB')
