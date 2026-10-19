"""Geração de arquivos para o fluxo de pesquisa reputacional."""

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


def save_product_results(
    records: list[NewsRecord], output_dir: Path, product: str
) -> Path:
    """Salva o relatório de um produto."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_product = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in product
    ).strip("_") or "produto"
    destination = output_dir / f"pesquisa_bing_{safe_product}_{timestamp}.xlsx"
    _frame_from_records(records).write_excel(
        destination, worksheet="Resultados", autofit=True
    )
    return destination
