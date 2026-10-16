# Pesquisa Reputacional

Aplicação Python que pesquisa marcas parceiras e termos relacionados à reputação no Bing News ou no Google News e gera um relatório Excel. A implementação mantém o fluxo principal em `app.py`, o contrato abstrato e as implementações dos mecanismos em `engines/`, e todas as configurações em `config.py`.

## Estrutura do projeto

```text
.
├── main.py                    # Launcher da aplicação na raiz
├── parceiros/
│   ├── marcas.xlsx              # Planilha de entrada (Gitignore!)
│   └── responsaveis.xlsx        # Produto, responsável e e-mail (Gitignore!)
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
│       ├── google.py            # Implementação do Google News
│       └── parsing.py           # Helpers compartilhados de parsing
├── tests/
│   ├── test_app.py              # Testes do fluxo, cache e relatórios
│   ├── test_bing.py             # Testes exclusivos do Bing
│   ├── test_google.py           # Testes exclusivos do Google
│   └── test_parsing.py          # Testes dos helpers compartilhados
├── pyproject.toml              # Metadados e dependências do pacote
└── README.md                   # Documentação do projeto
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

### Opção 2: pip no Python da máquina (VDI)

Em uma VDI dedicada ao projeto, também é possível instalar as dependências
diretamente no Python disponível na máquina, sem criar `.venv`. Essa opção é
mais simples para o usuário final. Na raiz do projeto, execute:

```bash
python3.11 -m pip install --user .
```

O parâmetro `--user` instala os pacotes apenas para o usuário atual. Depois da
instalação, execute normalmente:

```bash
pesquisa-reputacional
```

O `pip` lê o `pyproject.toml` durante a instalação: ele usa as dependências
declaradas no projeto e instala também o pacote local. Portanto, não é
necessário listar manualmente cada biblioteca usada pela aplicação.

## Execução

A entrada padrão é `parceiros/marcas.xlsx`, e os relatórios são gravados em `Resultados/`.

Com `uv`:

```bash
uv run pesquisa-reputacional
```

Com o Python da máquina instalado usando a Opção 2:

```bash
python3.11 main.py
```

Escolha o mecanismo de notícias com `--source` em qualquer uma das opções
(os valores aceitos são `bing` e `google`, em letras minúsculas):

```bash
uv run pesquisa-reputacional --source bing
uv run pesquisa-reputacional --source google
```

Ao usar `pip`, os comandos equivalentes são:

```bash
pesquisa-reputacional --source bing
pesquisa-reputacional --source google
```

Os mecanismos disponíveis estão organizados da seguinte forma:

```text
src/pesquisa_reputacional/engines/
├── base.py       # Contrato abstrato NewsSearchEngine
├── factory.py    # Registro e seleção dos mecanismos
├── bing.py       # Implementação do Bing News
├── google.py     # Implementação do Google News
└── parsing.py    # Helpers compartilhados de parsing
```

Para adicionar outro provedor, implemente `NewsSearchEngine` nessa pasta e registre a classe em `factory.py`.

As configurações operacionais de proxy e e-mail são carregadas automaticamente
do arquivo `.env` na raiz do projeto ou na pasta pai do projeto. Use
[.env.example](./.env.example) como
modelo e não versione o `.env` real, pois ele pode conter configurações
específicas do ambiente. As variáveis disponíveis são `NEWS_PROXY`,
`EMAIL_SENDER`, `EMAIL_CC`, `SMTP_HOST` e `SMTP_PORT`. O envio de e-mail
permanece habilitado no `Config` e não é configurado pelo `.env`.
Os valores padrão ficam em `src/pesquisa_reputacional/config.py`. As demais
configurações operacionais estão nesse arquivo: caminho de entrada, cadastro de
responsáveis, diretório de saída, limite de resultados, período, concorrência,
atraso, timeout, tentativas e sufixos. A linha de comando expõe
intencionalmente apenas `--source`.

O aplicativo mantém um cache de recuperação em `cache/` por padrão. Cada
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
cada commit enviado e em pipelines de merge request. O job instala as
dependências declaradas no `pyproject.toml`, executa toda a suíte Pytest e publica o relatório JUnit nos
resultados de testes do pipeline.

A planilha `parceiros/marcas.xlsx` deve conter as colunas `MARCA` e `PRODUTO`. É possível informar vários produtos na mesma célula, separados por vírgula ou ponto e vírgula. Cada marca é combinada com os seguintes termos: `acusada`, `corrupção`, `denuncia`, `investigada`, `condenada`, `assédio`, `fraude` e `Recuperação Judicial`.

O arquivo `parceiros/responsaveis.xlsx` deve conter uma linha por produto e as
colunas `PRODUTO`, `RESPONSAVEL` e `EMAIL`. O nome do produto é normalizado em
maiúsculas, sem espaços nas extremidades, para o relacionamento com
`marcas.xlsx`. A execução falha antes do envio se algum produto não tiver
responsável cadastrado.

O relatório Excel consolidado usa nomes de colunas em português: `fonte`,
`marca`, `produto`, `sufixo`, `consulta`, `título`, `resumo`, `origem`,
`data_publicação`, `data_texto`, `link`, `data_coleta`, `status_http`, `status`
e `erro`. Também é gerado um arquivo por produto em `Resultados/`. Quando
`email_enabled` está habilitado, cada arquivo por produto é enviado ao
responsável com `belotto@bb.com.br` em cópia. O remetente e o SMTP podem ser
alterados pelas variáveis `EMAIL_SENDER`, `EMAIL_CC` e `SMTP_HOST`; para
desabilitar o envio em uma execução, use `Config(email_enabled=False)`.

## Observações

As páginas HTML de notícias não são APIs públicas estáveis. Alterações de
layout, limitação de requisições, CAPTCHA, personalização e políticas de rede
podem afetar os resultados. O relatório registra o mecanismo selecionado, o
status da coleta e os erros, em vez de tratar falhas técnicas como pesquisas
sem resultados. Uma falha registrada no cache não será pesquisada novamente
até a expiração do cache. No Bing, o parser ignora links internos de busca e
prioriza o link externo da notícia quando ele está disponível. No Google, o
resultado pode conter um link intermediário `news.google.com`; a resolução
desse redirecionamento para o domínio original da notícia ainda depende do
acesso ao Google e da resposta do provedor. A coleta deve respeitar os termos
e as políticas aplicáveis de cada provedor.
