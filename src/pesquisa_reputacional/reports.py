"""Report output for the reputation research workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from .model import NewsRecord

def save_results(records: list[NewsRecord], output_dir: Path, source: str) -> Path:
    """Save a timestamped Excel report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [record.model_dump(by_alias=True) for record in records]
    frame = (
        pl.DataFrame(rows)
        if rows
        else pl.DataFrame([NewsRecord().model_dump(by_alias=True)]).clear()
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"pesquisa_{source}_{timestamp}.xlsx"
    frame.write_excel(destination, worksheet="Resultados", autofit=True)
    return destination
