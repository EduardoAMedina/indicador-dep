"""Baixa a lista de municípios do IBGE de um ano: a Divisão Territorial Brasileira (DTB).

Fonte: https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/<ano>/DTB_<ano>.zip
A DTB de cada ano traz os municípios instalados até a data-base daquele ano. O vínculo da RAIS só recebe resultado
municipal se o código do município estiver na DTB do mesmo ano (ver 2_tratamento/tratar_municipios.py).

Uso: python 1_download/baixar_municipios.py 2025
"""
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import ano_do_argumento, log, md5, pasta, registrar_no_manifesto  # noqa: E402

ENDERECO = 'https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/divisao_territorial/{ano}/DTB_{ano}.zip'

if __name__ == '__main__':
    ano = ano_do_argumento()
    # endereço da DTB do ano; o arquivo vai para brutos/<ano>/
    endereco = ENDERECO.format(ano=ano)
    destino = pasta('brutos', ano) / f'DTB_{ano}.zip'
    # baixa o .zip e guarda a data de modificação informada pelo servidor do IBGE
    with urllib.request.urlopen(endereco, timeout=120) as resposta:
        data = resposta.headers.get('Last-Modified', '')
        destino.write_bytes(resposta.read())
    # registra o arquivo no manifesto do ano
    registrar_no_manifesto(destino.parent / 'manifesto.csv', {
        'fonte': 'Divisão Territorial Brasileira (IBGE)', 'endereco': endereco, 'arquivo': destino.name,
        'bytes': destino.stat().st_size, 'data_na_fonte': data, 'baixado_em': time.strftime('%Y-%m-%d'), 'md5': md5(destino)})
    log(f'{destino.name}: {destino.stat().st_size / 1e6:.1f} MB')
