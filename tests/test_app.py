"""Unit tests for the application workflow, cache and Excel output."""

import os
from pathlib import Path
import time
from typing import Any
import warnings

import polars as pl
import pytest

from pesquisa_reputacional.app import collect, make_queries, read_brands, save_results
from pesquisa_reputacional.config import Config
from pesquisa_reputacional.engines.base import NewsSearchEngine
from pesquisa_reputacional.engines.factory import create_engine


class FakeEngine(NewsSearchEngine):
    """In-memory engine used to test the workflow without network access."""

    source_name = "fake"

    def __init__(self) -> None:
        super().__init__(limit=1, days=60, concurrency=2, delay=0, timeout=1, retries=0, proxy=None)
        self.calls: list[str] = []

    def search(self, query: str) -> list[dict[str, object]]:
        self.calls.append(query)
        return [{
            "título": query,
            "resumo": "Resumo",
            "origem": "Fonte",
            "data_publicação": None,
            "data_texto": None,
            "link": f"https://example.com/{len(self.calls)}",
            "status_http": 200,
            "status": "success",
            "erro": None,
        }]


def test_make_queries_combines_brands_and_suffixes() -> None:
    """Each brand is combined with every configured suffix."""
    queries = make_queries(["MARCA A", "MARCA B"], ["fraude", "corrupção"])

    assert len(queries) == 4
    assert queries[0] == ("MARCA A", "fraude", '"MARCA A" "fraude"')


def test_make_queries_normalizes_spaces_and_punctuation() -> None:
    """Query text removes separators and repeated whitespace from brands."""
    queries = make_queries(["  Marca,  Exemplo; S.A.  "], ["fraude"])

    assert queries == [("  Marca,  Exemplo; S.A.  ", "fraude", '"Marca Exemplo S.A." "fraude"')]


def test_read_brands_cleans_deduplicates_and_sorts(tmp_path: Path) -> None:
    """Brand input is normalized before queries are generated."""
    input_path = tmp_path / "marcas.xlsx"
    pl.DataFrame({"MARCA": ["  Beta  ", "alpha", "ALPHA", None, ""]}).write_excel(input_path)

    assert read_brands(input_path) == ["ALPHA", "BETA"]


def test_read_brands_rejects_missing_marca_column(tmp_path: Path) -> None:
    """A workbook without MARCA raises a descriptive validation error."""
    input_path = tmp_path / "marcas.xlsx"
    pl.DataFrame({"NOME": ["MARCA A"]}).write_excel(input_path)

    with pytest.raises(ValueError, match="must contain a 'MARCA' column"):
        read_brands(input_path)


def test_collect_resumes_from_cache(tmp_path: Path) -> None:
    """Completed queries are skipped when collection resumes."""
    queries = [
        ("A", "fraude", '"A" "fraude"'),
        ("B", "fraude", '"B" "fraude"'),
        ("C", "fraude", '"C" "fraude"'),
    ]
    cache_path = tmp_path / "bing_consultas.jsonl"

    first_engine = FakeEngine()
    collect(queries[:2], first_engine, cache_path)

    second_engine = FakeEngine()
    records = collect(queries, second_engine, cache_path)

    assert second_engine.calls == [queries[2][2]]
    assert len(records) == 3


def test_collect_empty_queries_returns_empty_list(tmp_path: Path) -> None:
    """An empty input does not invoke the engine or create records."""
    engine = FakeEngine()

    assert collect([], engine, tmp_path / "cache.jsonl") == []
    assert engine.calls == []


def test_collect_restarts_expired_cache(tmp_path: Path) -> None:
    """Expired cache entries are removed and their queries are collected again."""
    query = ("A", "fraude", '"A" "fraude"')
    cache_path = tmp_path / "bing_consultas.jsonl"

    first_engine = FakeEngine()
    collect([query], first_engine, cache_path)
    expired_timestamp = time.time() - (8 * 24 * 60 * 60)
    os.utime(cache_path, (expired_timestamp, expired_timestamp))

    second_engine = FakeEngine()
    records = collect([query], second_engine, cache_path)

    assert second_engine.calls == [query[2]]
    assert len(records) == 1


def test_collect_uses_configured_cache_validity(tmp_path: Path) -> None:
    """The configured cache validity controls when entries expire."""
    query = ("A", "fraude", '"A" "fraude"')
    cache_path = tmp_path / "bing_consultas.jsonl"

    first_engine = FakeEngine()
    collect([query], first_engine, cache_path)
    expired_timestamp = time.time() - (2 * 24 * 60 * 60)
    os.utime(cache_path, (expired_timestamp, expired_timestamp))

    second_engine = FakeEngine()
    collect([query], second_engine, cache_path, cache_max_age_days=1)

    assert second_engine.calls == [query[2]]


def test_save_results_writes_expected_columns(tmp_path: Path) -> None:
    """The Excel report contains the Portuguese output contract."""
    record = {
        "fonte": "bing",
        "marca": "MARCA A",
        "sufixo": "fraude",
        "consulta": '"MARCA A" "fraude"',
        "título": "Notícia",
        "resumo": "Resumo",
        "origem": "Fonte",
        "data_publicação": None,
        "data_texto": "hoje",
        "link": "https://example.com",
        "data_coleta": "2026-09-10T00:00:00+00:00",
        "status_http": 200,
        "status": "success",
        "erro": None,
    }

    output = save_results([record], tmp_path, "bing")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"from_arrow\(.*will return a Series instead of a DataFrame.*",
            category=FutureWarning,
        )
        frame = pl.read_excel(output)

    assert frame.columns == [
        "fonte", "marca", "sufixo", "consulta", "título", "resumo",
        "origem", "data_publicação", "data_texto", "link", "data_coleta",
        "status_http", "status", "erro",
    ]


def test_save_results_writes_empty_report_with_expected_columns(tmp_path: Path) -> None:
    """An empty collection still produces a valid report schema."""
    output = save_results([], tmp_path, "bing")

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"from_arrow\(.*will return a Series instead of a DataFrame.*",
            category=FutureWarning,
        )
        frame = pl.read_excel(output)

    assert frame.columns == [
        "fonte", "marca", "sufixo", "consulta", "título", "resumo",
        "origem", "data_publicação", "data_texto", "link", "data_coleta",
        "status_http", "status", "erro",
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", " "),
        ("cache_max_age_days", 0),
        ("result_limit", 0),
        ("days", 0),
        ("concurrency", 0),
        ("delay_seconds", -1),
        ("timeout_seconds", 0),
        ("retries", -1),
    ],
)
def test_config_rejects_invalid_values(field: str, value: Any) -> None:
    """Invalid operational settings fail before network activity starts."""
    config = Config(**{field: value})

    with pytest.raises(ValueError):
        config.validate()


def test_factory_rejects_unknown_engine() -> None:
    """Unknown source names produce a descriptive factory error."""
    with pytest.raises(ValueError, match="Unsupported news engine"):
        create_engine("unknown", limit=1, days=1, concurrency=1, delay=0, timeout=1, retries=0, proxy=None)
