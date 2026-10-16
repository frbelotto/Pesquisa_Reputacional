"""Single place for application configuration."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = (
    PROJECT_ROOT / ".env"
    if (PROJECT_ROOT / ".env").is_file()
    else PROJECT_ROOT.parent / ".env"
)


class Config(BaseSettings):
    """Settings used by the reputation research."""

    model_config = SettingsConfigDict(
        frozen=True,
        validate_default=True,
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    source: str = "bing"
    input_path: Path = Path("parceiros/marcas.xlsx")
    responsible_path: Path = Path("parceiros/responsaveis.xlsx")
    output_dir: Path = Path("Resultados")
    cache_dir: Path = Path("cache")
    cache_enabled: bool = True
    cache_max_age_days: int = Field(default=7, ge=1)
    result_limit: int = Field(default=10, ge=1)
    days: int = Field(default=60, ge=1)
    concurrency: int = Field(default=3, ge=1)
    delay_seconds: float = Field(default=1.0, ge=0)
    timeout_seconds: float = Field(default=20.0, gt=0)
    retries: int = Field(default=2, ge=0)
    proxy: str | None = Field(
        default="http://cachebb.proxy:80",
        validation_alias="NEWS_PROXY",
    )
    email_enabled: bool = True
    email_sender: str = "lukas.barcellos@bb.com.br"
    email_cc: str = "belotto@bb.com.br"
    smtp_host: str = "smtp.bb.com.br"
    smtp_port: int = Field(default=25, ge=1, le=65535)
    suffixes: list[str] = Field(default_factory=lambda: [
        "acusada",
        "corrupção",
        "denuncia",
        "investigada",
        "condenada",
        "assédio",
        "fraude",
        "Recuperação Judicial",
    ])

    @field_validator("source")
    @classmethod
    def source_must_not_be_empty(cls, value: str) -> str:
        """Reject empty or whitespace-only engine names."""
        if not value.strip():
            raise ValueError("source must not be empty")
        return value


CONFIG = Config()
