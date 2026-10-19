"""Ponto central da configuração da aplicação."""

import random
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = (
    PROJECT_ROOT / ".env"
    if (PROJECT_ROOT / ".env").is_file()
    else PROJECT_ROOT.parent / ".env"
)


class Config(BaseSettings):
    """Configurações da aplicação; segredos e endpoints vêm do `.env`."""

    model_config = SettingsConfigDict(
        frozen=True,
        validate_default=True,
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        # Rejeita cedo variáveis de ambiente com erro de digitação ou não documentadas.
        extra="forbid",
    )

    # Arquivos de entrada e saída. Os caminhos são relativos à pasta de execução.
    input_path: Path = Path("parceiros/marcas.xlsx")
    responsible_path: Path = Path("parceiros/responsaveis.xlsx")
    output_dir: Path = Path("Resultados")

    # Controles da pesquisa no Bing. O limite e o período têm padrões locais
    # por serem escolhas operacionais, não credenciais.
    result_limit: int = Field(default=10, ge=1)
    days: int = Field(default=30, ge=1)
    # Um novo atraso aleatório é escolhido a cada execução para evitar um padrão
    # fixo de requisições. Ele não é lido de uma configuração secreta.
    delay_seconds: float = Field(
        default_factory=lambda: random.uniform(0.5, 1.5),
        ge=0.5,
        le=1.5,
    )
    timeout_seconds: float = Field(default=20.0, gt=0)
    retries: int = Field(default=2, ge=0)

    # Valores de rede e e-mail devem ser fornecidos pelo arquivo `.env` local.
    # Nomes de infraestrutura, endereços e portas não ficam no código-fonte.
    proxy: str | None = Field(validation_alias="NEWS_PROXY")

    # Use EMAIL_ENABLED=false quando quiser gerar relatórios sem SMTP.
    email_enabled: bool = True
    email_sender: str = Field(validation_alias="EMAIL_SENDER")
    email_cc: str = Field(validation_alias="EMAIL_CC")
    smtp_host: str = Field(validation_alias="SMTP_HOST")
    smtp_port: int = Field(validation_alias="SMTP_PORT", ge=1, le=65535)


# O BaseSettings completa os campos obrigatórios lendo o arquivo `.env`.
CONFIG = Config(**{})
