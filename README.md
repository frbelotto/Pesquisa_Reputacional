# Pesquisa Reputacional

Aplicação Python que pesquisa marcas parceiras e termos relacionados à reputação no Bing News ou no Google News e gera um relatório Excel. A implementação mantém o fluxo principal em `app.py`, o contrato abstrato e as implementações dos mecanismos em `engines/`, e todas as configurações em `config.py`.

## Estrutura do projeto

```text
.
├── main.py                    # Launcher da aplicação na raiz
├── parceiros/
│   └── marcas.xlsx              # Planilha de entrada (Gitignore!)
├── Resultados/                 # Relatórios Excel gerados (Gitignore!)
├── src/pesquisa_reputacional/
│   ├── __init__.py             # Ponto de entrada público do pacote
│   ├── app.py                  # Orquestração do fluxo de pesquisa e CLI
│   ├── cache.py                # Cache JSONL e recuperação de execuções
│   ├── config.py               # Configurações da aplicação
│   ├── reports.py              # Geração dos relatórios Excel
│   └── engines/
│       ├── base.py             # Contrato abstrato NewsSearchEngine
│       ├── factory.py           # Registro e seleção dos mecanismos
│       ├── bing.py             # Implementação do Bing News
│       └── google.py            # Implementação do Google News
├── pyproject.toml              # Metadados e dependências do pacote
└── uv.lock                     # Versões bloqueadas das dependências
```

## Requisitos

- Python 3.11
- [uv](https://docs.astral.sh/uv/) (opcional)
- Acesso à rede do Bing News ou do Google News

Os comandos abaixo devem ser executados na raiz do projeto. Os caminhos padrão
de entrada, saída e cache são relativos ao diretório atual.

## Instalação

### Opção 1: uv

Na raiz do projeto:

```bash
uv sync
```

### Opção 2: pip

Crie e ative um ambiente virtual e instale o projeto a partir da raiz:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

No Windows PowerShell, use o seguinte comando de ativação:

```powershell
.venv\Scripts\Activate.ps1
```

O projeto não exige o `uv`; o `pip` lê as dependências diretamente do
`pyproject.toml`.

## Execução

A entrada padrão é `parceiros/marcas.xlsx`, e os relatórios são gravados em `Resultados/`.

Com `uv`:

```bash
uv run python main.py
```

Com o ambiente virtual instalado usando `pip`:

```bash
python main.py
```

Escolha o mecanismo de notícias com `--source` em qualquer uma das opções
(os valores aceitos são `bing` e `google`, em letras minúsculas):

```bash
uv run python main.py --source bing
uv run python main.py --source google
```

Ao usar `pip`, os comandos equivalentes são:

```bash
python main.py --source bing
python main.py --source google
```

Os mecanismos disponíveis estão organizados da seguinte forma:

```text
src/pesquisa_reputacional/engines/
├── base.py       # Contrato abstrato NewsSearchEngine
├── factory.py    # Registro e seleção dos mecanismos
├── bing.py       # Implementação do Bing News
└── google.py     # Implementação do Google News
```

Para adicionar outro provedor, implemente `NewsSearchEngine` nessa pasta e registre a classe em `factory.py`.

Todas as configurações operacionais estão em `src/pesquisa_reputacional/config.py`: caminho de entrada, diretório de saída, limite de resultados, período, concorrência, atraso, timeout, tentativas, proxy e sufixos. A linha de comando expõe intencionalmente apenas `--source`. O proxy de fallback padrão (`http://cachebb.proxy:80`) é específico da rede corporativa e pode ser alterado pela variável de ambiente `NEWS_PROXY`.

O aplicativo mantém um cache de recuperação em `.cache/` por padrão. Cada
consulta concluída, inclusive uma consulta sem resultados ou com falha, é
escrita imediatamente em um arquivo JSONL, para que uma execução interrompida
possa reiniciar e pular consultas já registradas. O cache expira após sete dias
e é removido apenas após o relatório final em Excel ser escrito com sucesso.
O progresso é exibido com uma barra `tqdm` mostrando consultas concluídas sobre
o total.

## Testes

Os testes são unitários e não acessam Bing, Google ou qualquer proxy real. As conexões HTTP são simuladas com mocks, incluindo sucesso, erro direto, fallback de proxy e falha do proxy:

```bash
uv run pytest -q
```

## Integração contínua

O repositório inclui `.gitlab-ci.yml`. O GitLab executa o job `unit-tests` a
cada commit enviado e em pipelines de merge request. O job instala o ambiente
`uv` bloqueado, executa toda a suíte Pytest e publica o relatório JUnit nos
resultados de testes do pipeline.

A planilha deve conter uma coluna `MARCA`. Cada marca é combinada com os seguintes termos: `acusada`, `corrupção`, `denuncia`, `investigada`, `condenada`, `assédio`, `fraude` e `Recuperação Judicial`.

O relatório Excel gerado usa nomes de colunas em português: `fonte`, `marca`, `sufixo`, `consulta`, `título`, `resumo`, `origem`, `data_publicação`, `data_texto`, `link`, `data_coleta`, `status_http`, `status` e `erro`. Nenhum identificador de execução é gerado, pois ele não é necessário para o relatório.

## Observações

As páginas HTML de notícias não são APIs públicas estáveis. Alterações de
layout, limitação de requisições, CAPTCHA, personalização e políticas de rede
podem afetar os resultados. O relatório registra o mecanismo selecionado, o
status da coleta e os erros, em vez de tratar falhas técnicas como pesquisas
sem resultados. Uma falha registrada no cache não será pesquisada novamente
até a expiração do cache. A coleta deve respeitar os termos e as políticas
aplicáveis de cada provedor.
