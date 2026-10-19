"""Testes unitários do fluxo simplificado do Bing."""

from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from pesquisa_reputacional.app import (
    collect,
    make_queries,
    read_brand_products,
    read_responsibles,
)
from pesquisa_reputacional.config import Config
from pesquisa_reputacional.email import send_report
from pesquisa_reputacional.model import NewsRecord
from pesquisa_reputacional.reports import save_product_results


class FakeBing:
    source_name = "bing"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, query: str) -> list[NewsRecord]:
        self.calls.append(query)
        return [NewsRecord.model_validate({
            "title": query,
            "http_status": 200,
            "status": "success",
        })]


def test_make_queries_uses_fixed_reputation_terms() -> None:
    queries = make_queries(["MARCA A"])

    assert len(queries) == 8
    assert queries[0] == ('MARCA A', "acusada", '"MARCA A" "acusada"')
    assert queries[-1] == (
        "MARCA A",
        "Recuperação Judicial",
        '"MARCA A" "Recuperação Judicial"',
    )


def test_make_queries_normalizes_brand_spaces_and_punctuation() -> None:
    assert make_queries(["  Marca,  Exemplo; S.A.  "])[0] == (
        "  Marca,  Exemplo; S.A.  ",
        "acusada",
        '"Marca Exemplo S.A." "acusada"',
    )


def test_read_brand_products_splits_and_normalizes_values(tmp_path: Path) -> None:
    input_path = tmp_path / "marcas.xlsx"
    pl.DataFrame({
        "MARCA": [" Casas Bahia ", "Amazon.com.br"],
        "PRODUTO": ["E2E, AFILIADOS", "afiliados"],
    }).write_excel(input_path)

    assert read_brand_products(input_path) == {
        "AMAZON.COM.BR": ["AFILIADOS"],
        "CASAS BAHIA": ["E2E", "AFILIADOS"],
    }


def test_read_responsibles_reads_product_mapping(tmp_path: Path) -> None:
    input_path = tmp_path / "responsaveis.xlsx"
    pl.DataFrame({
        "PRODUTO": [" afiliados "],
        "RESPONSAVEL": ["Ana Silva"],
        "EMAIL": ["ana@example.com"],
    }).write_excel(input_path)

    assert read_responsibles(input_path) == {
        "AFILIADOS": ("Ana Silva", "ana@example.com")
    }


def test_collect_runs_queries_sequentially_and_adds_metadata() -> None:
    queries = [("A", "fraude", '"A" "fraude"'), ("B", "fraude", '"B" "fraude"')]
    client = FakeBing()

    records = collect(queries, client)

    assert client.calls == ['"A" "fraude"', '"B" "fraude"']
    assert [(record.brand, record.source, record.suffix) for record in records] == [
        ("A", "bing", "fraude"),
        ("B", "bing", "fraude"),
    ]
    assert all(record.collected_at for record in records)


def test_collect_empty_queries_returns_empty_list() -> None:
    client = FakeBing()

    assert collect([], client) == []
    assert client.calls == []


def test_save_product_results_writes_expected_columns(tmp_path: Path) -> None:
    record = NewsRecord.model_validate({
        "source": "bing",
        "brand": "MARCA A",
        "product": "AFILIADOS",
        "suffix": "fraude",
        "query": '"MARCA A" "fraude"',
        "title": "Notícia",
        "status": "success",
    })

    output = save_product_results([record], tmp_path, "AFILIADOS")
    frame = pl.read_excel(output)

    assert output.name.startswith("pesquisa_bing_AFILIADOS_")
    assert frame.columns == [
        "fonte", "marca", "produto", "sufixo", "consulta", "título", "resumo",
        "origem", "data_publicação", "data_texto", "link", "data_coleta",
        "status_http", "status", "erro",
    ]


def test_send_report_uses_responsible_and_fixed_copy(tmp_path: Path) -> None:
    report = tmp_path / "relatorio.xlsx"
    report.write_bytes(b"excel content")
    config = Config(
        email_sender="sender@example.com",
        email_cc="belotto@bb.com.br",
        smtp_host="smtp.example.com",
    )

    with patch("pesquisa_reputacional.email.smtplib.SMTP") as smtp_class:
        send_report(report, "AFILIADOS", "Ana Silva", "ana@example.com", config)

    smtp = smtp_class.return_value.__enter__.return_value
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "ana@example.com"
    assert message["Cc"] == "belotto@bb.com.br"
    assert [part.get_filename() for part in message.iter_attachments()] == ["relatorio.xlsx"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("result_limit", 0),
        ("days", 0),
        ("delay_seconds", -1),
        ("timeout_seconds", 0),
        ("retries", -1),
        ("smtp_port", 0),
    ],
)
def test_config_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        Config(**{field: value})
