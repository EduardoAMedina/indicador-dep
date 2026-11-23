"""Caminhos e funções usados por todos os processadores do indicador DEP.

Pastas (todas dentro de DEP_DADOS; por padrão, indicador_dep/dados):
    brutos/<ano>/      arquivos baixados das fontes, sem alteração, e o manifesto do download
    brutos/cbo/        tabela de famílias da CBO
    tratados/<ano>/    arquivos intermediários, um por etapa
    entrega/<ano>/     tabela de contagens e dicionários do ano

No Windows, use uma pasta de caminho curto e sem acento em DEP_DADOS (por exemplo, C:/dep): o 7-Zip e o DuckDB
falham em caminhos longos ou com acento.
"""
import csv
import hashlib
import os
import sys
import time
from pathlib import Path

# Pasta deste código. Os dados ficam fora dela, em DEP_DADOS, porque somam vários GB e não são versionados.
AQUI = Path(__file__).resolve().parent
DADOS = Path(os.environ.get('DEP_DADOS', AQUI / 'dados'))
SETE_Z = os.environ.get('DEP_7Z', '7z')   # executável do 7-Zip (7z ou 7zr); os microdados da RAIS vêm em .7z


def pasta(*partes):
    """Devolve uma pasta dentro de DEP_DADOS, criando-a se preciso."""
    p = DADOS.joinpath(*map(str, partes))
    p.mkdir(parents=True, exist_ok=True)
    return p


def ano_do_argumento():
    """Lê o ano-base da linha de comando (python <processador>.py 2025). A série publicada começa em 2023."""
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) < 2023:
        raise SystemExit(f'Uso: python {Path(sys.argv[0]).name} <ano>, com ano 2023 ou posterior')
    return int(sys.argv[1])


def log(*mensagem):
    print(time.strftime('%H:%M:%S'), *mensagem, flush=True)


def md5(caminho):
    """Código de verificação do arquivo, para saber se outra pessoa baixou exatamente o mesmo arquivo."""
    h = hashlib.md5()
    with open(caminho, 'rb') as f:
        # lê o arquivo em blocos de 1 MB, para não carregar arquivos de vários GB na memória
        for bloco in iter(lambda: f.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


# Colunas do manifesto: de onde veio cada arquivo, quando foi baixado e como conferir que é o mesmo (md5).
CAMPOS_MANIFESTO = ['fonte', 'endereco', 'arquivo', 'bytes', 'data_na_fonte', 'baixado_em', 'md5']


def registrar_no_manifesto(manifesto, linha):
    """Acrescenta (ou atualiza) a linha de um arquivo no manifesto do download (CSV em UTF-8)."""
    # lê o manifesto que já existe, sem a linha antiga deste arquivo (caso ele tenha sido baixado de novo)
    linhas = []
    if manifesto.exists():
        with open(manifesto, encoding='utf-8', newline='') as f:
            linhas = [l for l in csv.DictReader(f) if l['arquivo'] != linha['arquivo']]
    # acrescenta a linha nova e regrava o manifesto inteiro, em ordem de fonte e de arquivo
    linhas.append(linha)
    with open(manifesto, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_MANIFESTO)
        w.writeheader()
        w.writerows(sorted(linhas, key=lambda l: (l['fonte'], l['arquivo'])))
