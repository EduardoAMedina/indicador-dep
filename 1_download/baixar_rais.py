"""Baixa os microdados de vínculos da RAIS de um ano-base, do FTP do Ministério do Trabalho e Emprego (MTE).

Fonte: ftp://ftp.mtps.gov.br/pdet/microdados/RAIS/<ano>/
- Baixa só os arquivos de vínculos (.7z) da pasta principal do ano: de 2023 em diante, seis regionais e um de município
  não identificado (NI). Ficam de fora os arquivos de estabelecimentos (ESTB) e as subpastas, como "Legado" e "Parcial",
  que guardam versões anteriores ou incompletas.
- Se a conexão cair, rodar de novo continua de onde parou. Um arquivo só conta como baixado quando o tamanho bate com o
  informado pelo FTP.
- Cada arquivo entra no manifesto (brutos/<ano>/manifesto.csv) com tamanho, data no FTP e md5. O MTE regenera os
  microdados de tempos em tempos; o manifesto registra qual versão foi usada.

Uso: python 1_download/baixar_rais.py 2025
"""
import ftplib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comum import ano_do_argumento, log, md5, pasta, registrar_no_manifesto  # noqa: E402

# Servidor FTP público do MTE com os microdados da RAIS.
SERVIDOR = 'ftp.mtps.gov.br'


def conectar(ano):
    # o FTP do MTE lista nomes em Latin-1 (a pasta de 2023 tem um nome acentuado que quebra a leitura em UTF-8)
    ftp = ftplib.FTP(SERVIDOR, timeout=120, encoding='latin-1')
    ftp.login()                                   # acesso anônimo
    ftp.cwd(f'/pdet/microdados/RAIS/{ano}/')
    ftp.voidcmd('TYPE I')                         # modo binário, necessário para SIZE e para o download
    return ftp


def arquivos_de_vinculos(ftp):
    """Arquivos .7z da pasta do ano, sem os de estabelecimentos. As subpastas não terminam em .7z e ficam de fora."""
    nomes = [n for n in ftp.nlst() if n.lower().endswith('.7z') and 'ESTB' not in n.upper() and 'ESTAB' not in n.upper()]
    if not nomes:
        raise SystemExit('Nenhum arquivo de vínculos na pasta do ano.')
    return sorted(nomes)


def data_no_ftp(ftp, nome):
    try:
        return ftp.sendcmd(f'MDTM {nome}').split()[-1]   # AAAAMMDDhhmmss
    except ftplib.error_perm:
        return ''


def baixar(ftp, ano, nome, destino, tamanho):
    """Baixa o arquivo, continuando de onde parou (comando REST) se já houver uma parte em disco.
    Devolve a conexão em uso, que pode ter sido refeita depois de uma queda."""
    # até 5 tentativas: a cada queda, a conexão é refeita e o download continua de onde parou
    for tentativa in range(5):
        # quanto do arquivo já está em disco (0 se ainda não começou); se está completo, passa ao próximo
        feito = destino.stat().st_size if destino.exists() else 0
        if feito == tamanho:
            return ftp
        try:
            # 'ab' acrescenta ao fim do arquivo; rest=feito pede ao FTP que comece daquele byte
            with open(destino, 'ab') as f:
                ftp.retrbinary(f'RETR {nome}', f.write, blocksize=1 << 20, rest=feito or None)
        except ftplib.all_errors as e:
            log(f'{nome}: falha ({e}); nova tentativa em 30 s')
            time.sleep(30)
            for espera in (30, 60, 120, 240):             # a rede pode voltar aos poucos (até o DNS falha às vezes)
                try:
                    ftp = conectar(ano)
                    break
                except (ftplib.all_errors, OSError) as e2:
                    log(f'reconexão falhou ({e2}); nova tentativa em {espera} s')
                    time.sleep(espera)
    # depois das tentativas, o arquivo precisa ter exatamente o tamanho informado pelo FTP
    if not destino.exists() or destino.stat().st_size != tamanho:
        raise SystemExit(f'{nome}: download incompleto')
    return ftp


if __name__ == '__main__':
    ano = ano_do_argumento()
    # os arquivos do ano vão para brutos/<ano>/
    saida = pasta('brutos', ano)
    ftp = conectar(ano)
    # baixa cada arquivo de vínculos e registra no manifesto o endereço, o tamanho, a data no FTP e o md5
    for nome in arquivos_de_vinculos(ftp):
        tamanho = ftp.size(nome)
        destino = saida / nome
        ftp = baixar(ftp, ano, nome, destino, tamanho)
        registrar_no_manifesto(saida / 'manifesto.csv', {
            'fonte': 'RAIS vínculos (MTE)', 'endereco': f'ftp://{SERVIDOR}/pdet/microdados/RAIS/{ano}/{nome}', 'arquivo': nome,
            'bytes': tamanho, 'data_na_fonte': data_no_ftp(ftp, nome), 'baixado_em': time.strftime('%Y-%m-%d'), 'md5': md5(destino)})
        log(f'{nome}: {tamanho / 1e6:.0f} MB')
    ftp.quit()
