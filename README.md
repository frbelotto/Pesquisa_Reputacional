# Pesquisa Reputacional

Aplicação Python que pesquisa marcas parceiras e termos relacionados à reputação exclusivamente no Bing News. Para cada produto, gera um relatório Excel e pode enviá-lo por e-mail ao responsável.

## Estrutura

```text
.
├── main.py
├── parceiros/
│   ├── marcas.xlsx
│   └── responsaveis.xlsx
├── Resultados/
├── src/pesquisa_reputacional/
│   ├── app.py       # Leitura, consultas, coleta e envio
│   ├── config.py    # Configurações
│   ├── email.py     # Envio SMTP
│   ├── model.py     # Modelo dos registros
│   ├── reports.py   # Relatórios por produto
│   └── engines/
│       └── bing.py  # Requisição e parsing do Bing News
├── tests/
├── pyproject.toml
└── README.md
```

## Requisitos e instalação

- Python 3.11
- [uv](https://docs.astral.sh/uv/) (opcional)
- Acesso ao Bing News e ao servidor SMTP configurado

Na raiz do projeto, instale com `uv sync` ou com `python3.11 -m pip install --user .`.

## Execução

A execução usa `parceiros/marcas.xlsx` como entrada e grava os relatórios em `Resultados/`:

- Com uv: `uv run pesquisa-reputacional`
- Com Python instalado: `python3.11 main.py`

Não existe seleção de mecanismo: o Bing é a única fonte. A coleta é sequencial, sem cache, mantendo retries, timeout, atraso entre requisições e fallback de proxy. O atraso é sorteado entre 0,5 e 1,5 segundo a cada execução.

## Configuração

As configurações de proxy e e-mail são obrigatórias e devem ser carregadas de `.env` na raiz do projeto ou na pasta pai. Não há valores padrão desses campos no código. Use `.env.example` como modelo. As variáveis disponíveis são:

- `NEWS_PROXY`
- `EMAIL_SENDER`
- `EMAIL_CC`
- `SMTP_HOST`
- `SMTP_PORT`

Sem essas variáveis, a aplicação não inicia; isso evita enviar dados para um servidor incorreto por configuração implícita.

As demais configurações ficam em `src/pesquisa_reputacional/config.py`, incluindo caminhos, limite de resultados, período, timeout, retries, atraso e `email_enabled`.

Para executar sem enviar e-mail em um uso programático, passe `Config(email_enabled=False)` ao chamar `main`.

## Arquivos de entrada

`parceiros/marcas.xlsx` deve conter `MARCA` e `PRODUTO`. É possível informar vários produtos na mesma célula, separados por vírgula ou ponto e vírgula.

Cada marca é combinada com estes termos fixos:

- `acusada`
- `corrupção`
- `denuncia`
- `investigada`
- `condenada`
- `assédio`
- `fraude`
- `Recuperação Judicial`

`parceiros/responsaveis.xlsx` deve conter `PRODUTO`, `RESPONSAVEL` e `EMAIL`. A execução valida todos os produtos antes de pesquisar e falha se algum não tiver responsável cadastrado.

## Saída

É gerado um arquivo Excel por produto em `Resultados/`, com nomes como `pesquisa_bing_AFILIADOS_20261019_120000.xlsx`. O mesmo arquivo é anexado ao e-mail do responsável quando `email_enabled` está habilitado.

O relatório preserva as colunas `fonte`, `marca`, `produto`, `sufixo`, `consulta`, `título`, `resumo`, `origem`, `data_publicação`, `data_texto`, `link`, `data_coleta`, `status_http`, `status` e `erro`. Consultas sem resultado e falhas do Bing permanecem registradas para auditoria.

## Testes

Os testes não acessam o Bing nem o SMTP real. Execute a suíte com `uv run pytest -q`.

## Observações

As páginas HTML do Bing News não são uma API pública estável. Alterações de layout, CAPTCHA, limitação de requisições e políticas de rede podem afetar os resultados. O parser ignora links internos de busca e prioriza o link externo da notícia quando disponível.
