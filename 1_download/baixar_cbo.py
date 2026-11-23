"""Baixa a tabela de famílias ocupacionais da Classificação Brasileira de Ocupações (CBO), do portal do MTE.

Fonte: https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/cbo/servicos/downloads/cbo2002-familia.csv
O MTE publica só a versão atual da CBO, sem um arquivo por ano. A tabela serve para dar nome às famílias. Quais famílias
valem em cada ano sai da própria RAIS daquele ano: são as famílias declaradas nos vínculos (ver 3_contagem/gerar_dicionarios.py).
Como o arquivo muda sem aviso, o manifesto registra a data do download e o md5.

Uso: python 1_download/baixar_cbo.py
"""
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import log, md5, pasta, registrar_no_manifesto  # noqa: E402

ENDERECO = 'https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/cbo/servicos/downloads/cbo2002-familia.csv'

if __name__ == '__main__':
    # a tabela de famílias não depende do ano: fica em brutos/cbo/
    destino = pasta('brutos', 'cbo') / 'cbo2002-familia.csv'
    pedido = urllib.request.Request(ENDERECO, headers={'User-Agent': 'Mozilla/5.0'})   # o portal recusa pedidos sem navegador
    # baixa a tabela e guarda a data de modificação informada pelo portal
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        data = resposta.headers.get('Last-Modified', '')
        destino.write_bytes(resposta.read())
    # registra a data do download e o md5, porque a tabela muda sem aviso
    registrar_no_manifesto(destino.parent / 'manifesto.csv', {
        'fonte': 'Famílias da CBO 2002 (MTE)', 'endereco': ENDERECO, 'arquivo': destino.name, 'bytes': destino.stat().st_size,
        'data_na_fonte': data, 'baixado_em': time.strftime('%Y-%m-%d'), 'md5': md5(destino)})
    log(f'{destino.name}: {destino.stat().st_size / 1e3:.0f} kB')
