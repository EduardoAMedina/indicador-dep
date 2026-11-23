# Distância de Escolaridade do Posto (DEP): tabela de contagens

Este código gera, para cada ano-base da RAIS a partir de 2023, a tabela de contagens que a plataforma usa para calcular o DEP, e os dicionários que a acompanham. A plataforma faz o cálculo; o código só baixa as fontes, trata os microdados e conta os vínculos.

As tabelas e os dicionários de 2023, 2024 e 2025 já estão prontos na pasta `entrega/`. Para calcular o DEP, basta baixá-los e seguir as regras de "Como a plataforma calcula o DEP com a tabela", abaixo. Para conferir como foram feitos, rode o código: ele chega às mesmas tabelas a partir das fontes oficiais. A versão 1.0 deste repositório corresponde à primeira versão da nota metodológica do DEP.

## Requisitos

- Python 3.11 com o pacote `duckdb` (versão 1.5.6): `pip install duckdb==1.5.6`. O resto usa só a biblioteca padrão.
- 7-Zip, para descompactar os arquivos da RAIS (`7z` ou `7zr`).
- Uns 15 GB livres em disco por ano: cerca de 4 GB de arquivos baixados e, durante o tratamento, um arquivo descompactado de cada vez.
- Duas variáveis de ambiente:
  - `DEP_DADOS`: pasta dos dados (padrão: `indicador_dep/dados`). No Windows, use um caminho curto e sem acento, por exemplo `C:/dep`, porque o 7-Zip e o DuckDB falham em caminhos longos ou com acento.
  - `DEP_7Z`: caminho do executável do 7-Zip, se ele não estiver no PATH.

## Como rodar

Para um ano (2025, no exemplo), na pasta `indicador_dep`:

```
python 1_download/baixar_rais.py 2025
python 1_download/baixar_municipios.py 2025
python 1_download/baixar_cbo.py
python 2_tratamento/tratar_municipios.py 2025
python 2_tratamento/tratar_cbo.py
python 2_tratamento/tratar_rais.py 2025
python 3_contagem/contar_celulas.py 2025
python 3_contagem/gerar_dicionarios.py 2025
```

Cada processador faz uma etapa, lê o que o anterior gravou e pode ser rodado de novo sozinho. Para marcar as famílias novas no ano, rode antes o ano anterior: o dicionário de famílias compara com o do ano anterior, quando ele existe.

| Etapa | Processador | O que faz | Grava em |
| --- | --- | --- | --- |
| Download | `baixar_rais.py` | Arquivos de vínculos (.7z) da pasta do ano no FTP do MTE, sem estabelecimentos nem subpastas | `brutos/<ano>/` |
| Download | `baixar_municipios.py` | Divisão Territorial Brasileira (DTB) do ano, do IBGE | `brutos/<ano>/` |
| Download | `baixar_cbo.py` | Tabela de famílias da CBO, do MTE | `brutos/cbo/` |
| Tratamento | `tratar_municipios.py` | Lista de municípios do ano, com código de 6 dígitos (o da RAIS) | `tratados/<ano>/municipios.csv` |
| Tratamento | `tratar_cbo.py` | Famílias da CBO em UTF-8 | `tratados/cbo/familias_cbo.csv` |
| Tratamento | `tratar_rais.py` | Estoque do ano divulgado pelo MTE (ativos em 31/12 sem abandono), códigos harmonizados, contagem por arquivo | `tratados/<ano>/rais/` |
| Contagem | `contar_celulas.py` | Confere o estoque com o divulgado pelo MTE, tira a faixa de 10 a 14 anos e soma as células | `entrega/<ano>/contagens_<ano>.csv.gz` |
| Contagem | `gerar_dicionarios.py` | Dicionários do ano e manifesto dos downloads | `entrega/<ano>/` |

Cada download registra no manifesto o endereço, o tamanho, a data na fonte, a data do download e o md5 do arquivo. O MTE regenera os microdados de tempos em tempos; o manifesto mostra qual versão foi usada.

## O que é entregue (pasta `entrega/<ano>/`)

Ao rodar o código, a entrega é gravada em `entrega/<ano>/` dentro de `DEP_DADOS`. A pasta `entrega/` deste repositório traz a mesma entrega de 2023, 2024 e 2025, gerada com este código em 22/11/2026.

- `contagens_<ano>.csv.gz`: uma linha por combinação de município, família da CBO, escolaridade, sexo, faixa etária, raça ou cor e setor, com o número de vínculos. Traz o universo do DEP: o estoque divulgado pelo MTE sem a faixa etária de 10 a 14 anos, que é trabalho infantil. Inclui os vínculos com escolaridade ou família inválida e os sem município, porque a plataforma precisa deles para a referência nacional, para o Brasil e para a cobertura. São cerca de 13 milhões de linhas por ano, por isso o formato é CSV compactado, e não planilha.
- `municipios_<ano>.csv`: os municípios da DTB do ano, inclusive os sem vínculos.
- `familias_cbo_<ano>.csv`: as famílias declaradas na RAIS do ano, que formam a estrutura ocupacional usada no ano, com o título, os vínculos no Brasil e as marcas de família nova no ano e de família ausente da tabela atual da CBO.
- `categorias.csv`: os códigos de cada variável, os grupos usados nos recortes e os anos de estudo de cada escolaridade.
- `colunas.csv`: o que é cada coluna e o formato da tabela.
- `universo_<ano>.csv`: o estoque do MTE, os vínculos de 10 a 14 anos retirados e o total da tabela.
- `manifesto_<ano>.csv`: os arquivos usados.

## Como a plataforma calcula o DEP com a tabela

As regras completas estão na nota metodológica (seções 4 a 6). Elas valem da mesma forma para qualquer unidade territorial: município, Unidade da Federação ou Brasil. Em resumo, para cada ano:

1. **Universo.** É a própria tabela: a faixa de 10 a 14 anos já saiu na contagem.
2. **Linhas válidas.** Entram na referência e no cálculo as linhas com escolaridade de 1 a 11 e família que identifica uma ocupação (`identifica_familia = sim` no dicionário de famílias).
3. **Referência nacional.** Para cada família, somar os vínculos válidos do Brasil por escolaridade, com todas as linhas, inclusive as sem município. A referência é a escolaridade com mais vínculos (a moda); em empate, a menor. Só têm referência as famílias com pelo menos 1.000 vínculos válidos no Brasil. A família tem referência frágil quando a diferença entre as duas escolaridades mais comuns é menor que 10 pontos percentuais. A referência e as famílias com referência não mudam com os filtros nem com a unidade territorial.
4. **Seleção.** Aplicar os filtros escolhidos (sexo, faixa etária, raça ou cor, setor), com os grupos de `categorias.csv`.
5. **Unidade territorial.** O município é `id_municipio`; a UF são os dois primeiros dígitos de `id_municipio`; o Brasil são todas as linhas, inclusive as sem município (`id_municipio` vazio), que não entram em nenhum município nem UF.
6. **Famílias incluídas.** Somar os vínculos válidos de cada família na unidade territorial, depois dos filtros. Entra a família com referência e pelo menos 10 vínculos nessa unidade territorial. O mínimo vale para cada unidade territorial, e não para cada município: uma família pode entrar na UF ou no Brasil sem ter 10 vínculos em nenhum dos seus municípios. Por isso, o DEP da UF não é a média dos seus municípios.
7. **Distância.** Cada vínculo de uma família incluída contribui com a diferença, em anos de estudo (`anos_de_estudo` em `categorias.csv`), entre a sua escolaridade e a referência da família: abaixo quando é menor, acima quando é maior.
8. **DEP da unidade territorial.** A soma das distâncias de todos os vínculos das famílias incluídas dividida pelo total desses vínculos (o que equivale a ponderar o DEP de cada família pelos seus vínculos). Os componentes abaixo e acima usam o mesmo denominador. O percentual fora da referência é a parcela dos vínculos incluídos com escolaridade diferente da referência. Sem nenhuma família incluída, o resultado é ausente, e não zero.
9. **Avisos e coberturas.** Aviso de base pequena quando a unidade territorial tem menos de 150 vínculos ou menos de 10 famílias incluídos, também nos recortes. Cobertura total: vínculos incluídos sobre todos os vínculos da unidade territorial na tabela, sem filtro (para o município, `vinculos` em `municipios_<ano>.csv`).

Para conferir o cálculo da plataforma, os valores da nota metodológica servem de referência:
- DEP do Brasil: 1,2363 em 2023, 1,2040 em 2024 e 1,1795 em 2025 (na nota, 1,24, 1,20 e 1,18);
- Minas Gerais, 2024: 1,3430;
- Belo Horizonte, 2024: 1,10 (0,66 abaixo e 0,44 acima), com 1.574.352 vínculos incluídos em 508 famílias.

## Tempo de execução

Medido com 2025, num notebook com Windows 11 (13/11/2026):

| Etapa | Tempo | Disco |
| --- | --- | --- |
| Download (7 arquivos da RAIS, DTB e CBO) | cerca de 15 minutos, conforme a conexão | 3,8 GB em `brutos/2025/` |
| `tratar_rais.py` | cerca de 8 minutos | até uns 6 GB temporários (um arquivo descompactado por vez) |
| `contar_celulas.py` | cerca de 1,5 minuto | |
| `gerar_dicionarios.py` | cerca de 10 segundos | |

O download depende muito do FTP do MTE. Em 22/11/2026, os de 2023 e 2024 levaram cerca de 40 e 80 minutos, com quedas de conexão que o script retomou sozinho; o tratamento levou 7 e 4 minutos.

| Ano | Linhas | Vínculos na tabela | Estoque do MTE | 10 a 14 anos (retirados) | Tamanho compactado |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023 | 12.739.634 | 55.308.864 | 55.316.614 | 7.750 | 42 MB |
| 2024 | 12.575.232 | 57.122.959 | 57.132.156 | 9.197 | 41 MB |
| 2025 | 12.982.125 | 59.960.079 | 59.970.945 | 10.866 | 43 MB |

## Conferências feitas

- 13/11/2026: a tabela de 2025 era igual, célula a célula, à base usada na nota, e o DEP calculado só com as regras deste README batia com o publicado nos 5.571 municípios.
- 22/11/2026, depois da mudança de metodologia (mínimo por unidade territorial e universo sem 10 a 14 anos): a contagem de 2025 foi refeita (o estoque lido continua igual ao do MTE, e a tabela fecha com ele somando a faixa retirada). Calculando o DEP só com a tabela, os dicionários e as regras acima, os 5.571 municípios, as 27 UFs e o Brasil (1,1795, com 59.922.120 vínculos incluídos) são iguais aos da nota.
- 22/11/2026, 2023 e 2024 rodados do zero com este código, com o mesmo resultado: o estoque lido é igual ao do MTE e, calculando só com a tabela, os dicionários e as regras acima, todos os municípios com DEP (5.569 em 2023 e 5.571 em 2024), as 27 UFs e o Brasil são iguais aos da nota. Brasil: 1,2363 em 2023 (55.252.738 vínculos incluídos) e 1,2040 em 2024 (57.074.825). Minas Gerais, 2024: 1,3430. Belo Horizonte, 2024: 1,1047, com 1.574.352 vínculos incluídos em 508 famílias.

## Licença e citação

- O código está na licença MIT (arquivo `LICENSE`): pode ser usado, modificado e redistribuído, desde que se mantenha o aviso de autoria.
- As tabelas e os dicionários de `entrega/` estão na licença Creative Commons Atribuição 4.0 Internacional (CC BY 4.0, arquivo `entrega/LICENSE.md`): qualquer uso, desde que se cite a fonte. São derivados de dados públicos (RAIS e CBO, do MTE; DTB, do IBGE), que também devem ser citados.

Como citar: MEDINA, Eduardo Alves. Distância de Escolaridade do Posto (DEP): código e tabelas de contagem. Versão 1.0. [S. l.]: GitHub, 2026. Disponível em: https://github.com/EduardoAMedina/indicador-dep.

Se o MTE regenerar os microdados ou a metodologia mudar, as tabelas novas entram numa nova versão do repositório, e as versões anteriores continuam disponíveis.
