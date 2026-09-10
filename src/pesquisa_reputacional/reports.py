"""Report output for the reputation research workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

OUTPUT_COLUMNS = [
    "fonte", "marca", "sufixo", "consulta", "título", "resumo", "origem",
    "data_publicação", "data_texto", "link", "data_coleta", "status_http",
    "status", "erro",
]


def save_results(records: list[dict[str, object]], output_dir: Path, source: str) -> Path:
    """Save a timestamped Excel report with Portuguese column names."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = pl.DataFrame(records) if records else pl.DataFrame({column: [] for column in OUTPUT_COLUMNS})
    frame = frame.select(OUTPUT_COLUMNS)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"pesquisa_{source}_{timestamp}.xlsx"
    frame.write_excel(destination, worksheet="Resultados", autofit=True)
    return destination
