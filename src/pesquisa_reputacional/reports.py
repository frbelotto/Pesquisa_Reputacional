"""Report output for the reputation research workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from .model import NewsRecord


REPORT_COLUMNS = [
    "fonte", "marca", "produto", "sufixo", "consulta", "título", "resumo",
    "origem", "data_publicação", "data_texto", "link", "data_coleta",
    "status_http", "status", "erro",
]


def _frame_from_records(records: list[NewsRecord]) -> pl.DataFrame:
    rows = [record.model_dump(by_alias=True) for record in records]
    frame = (
        pl.DataFrame(rows)
        if rows
        else pl.DataFrame([NewsRecord().model_dump(by_alias=True)]).clear()
    )
    return frame.select(REPORT_COLUMNS)


def save_results(records: list[NewsRecord], output_dir: Path, source: str) -> Path:
    """Save a timestamped Excel report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = _frame_from_records(records)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = output_dir / f"pesquisa_{source}_{timestamp}.xlsx"
    frame.write_excel(destination, worksheet="Resultados", autofit=True)
    return destination


def save_product_results(
    records: list[NewsRecord], output_dir: Path, source: str, product: str
) -> Path:
    """Save the report for one product."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_product = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in product
    ).strip("_") or "produto"
    destination = output_dir / f"pesquisa_{source}_{safe_product}_{timestamp}.xlsx"
    _frame_from_records(records).write_excel(
        destination, worksheet="Resultados", autofit=True
    )
    return destination
