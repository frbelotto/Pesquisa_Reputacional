"""Single place for application configuration."""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Config(BaseModel):
    """Settings used by the reputation research."""

    model_config = ConfigDict(frozen=True)

    source: str = "bing"
    input_path: Path = Path("parceiros/marcas.xlsx")
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
    proxy: str | None = os.getenv("NEWS_PROXY", "http://cachebb.proxy:80")
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
