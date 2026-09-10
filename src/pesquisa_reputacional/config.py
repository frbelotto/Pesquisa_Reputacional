"""Single place for application configuration."""

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Config:
    """Settings used by the reputation research."""

    source: str = "bing"
    input_path: Path = Path("parceiros/marcas.xlsx")
    output_dir: Path = Path("Resultados")
    cache_dir: Path = Path(".cache")
    cache_enabled: bool = True
    cache_max_age_days: int = 7
    result_limit: int = 10
    days: int = 60
    concurrency: int = 3
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    retries: int = 2
    proxy: str | None = os.getenv("NEWS_PROXY", "http://cachebb.proxy:80")
    suffixes: list[str] = field(default_factory=lambda: [
        "acusada",
        "corrupção",
        "denuncia",
        "investigada",
        "condenada",
        "assédio",
        "fraude",
        "Recuperação Judicial",
    ])

    def validate(self) -> None:
        """Validate the values before starting a collection."""
        if not self.source.strip():
            raise ValueError("source must not be empty")
        if (
            self.cache_max_age_days < 1
            or self.result_limit < 1
            or self.days < 1
            or self.concurrency < 1
        ):
            raise ValueError(
                "cache_max_age_days, result_limit, days and concurrency must be positive"
            )
        if self.delay_seconds < 0 or self.timeout_seconds <= 0 or self.retries < 0:
            raise ValueError("delay, timeout and retries have invalid values")


CONFIG = Config()
