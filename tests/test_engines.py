"""Unit tests for news engine HTTP behavior and parsers."""

from datetime import datetime
from typing import Any

import httpx
import pytest

from pesquisa_reputacional.engines.base import NewsSearchEngine
from pesquisa_reputacional.engines.bing import BingNewsClient, parse_articles, parse_date
from pesquisa_reputacional.engines.google import parse_google_articles


BING_HTML = """
<div class="news-card">
  <a class="title" href="https://example.com/news">Notícia de teste</a>
  <div class="snippet">Resumo da notícia</div>
  <div class="source">Fonte de teste</div>
  <span class="time">21d</span>
</div>
"""

GOOGLE_HTML = """
<article>
  <h3><a href="./articles/teste">Notícia Google</a></h3>
  <div class="source">Fonte Google</div>
  <time>21d</time>
  <p>Resumo Google</p>
</article>
"""


class MockHttpClient:
    """Context manager that simulates direct and proxy HTTP requests."""

    instances: list["MockHttpClient"] = []
    response: httpx.Response | None = None
    error: Exception | None = None
    fail_for_proxy = False

    def __init__(self, **kwargs: Any) -> None:
        self.proxy = kwargs.get("proxy")
        type(self).instances.append(self)

    def __enter__(self) -> "MockHttpClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def get(self, url: str, **_kwargs: Any) -> httpx.Response:
        if self.error is not None and (self.proxy is None or self.fail_for_proxy):
            request = httpx.Request("GET", url)
            raise httpx.ConnectError(str(self.error), request=request)
        if self.response is None:
            raise AssertionError("Mock response was not configured")
        return self.response


@pytest.fixture(autouse=True)
def reset_http_mock() -> None:
    """Reset mock state between tests."""
    MockHttpClient.instances = []
    MockHttpClient.response = None
    MockHttpClient.error = None
    MockHttpClient.fail_for_proxy = False


def make_client(proxy: str | None = None, retries: int = 0) -> BingNewsClient:
    """Create a client with fast settings for unit tests."""
    return BingNewsClient(
        limit=1,
        days=60,
        concurrency=1,
        delay=0,
        timeout=1,
        retries=retries,
        proxy=proxy,
    )


def test_bing_search_uses_mocked_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful mocked HTTP response becomes a normalized article."""
    MockHttpClient.response = httpx.Response(200, text=BING_HTML)
    monkeypatch.setattr(httpx, "Client", MockHttpClient)

    result = make_client().search('"Marca" "fraude"')

    assert result[0]["status"] == "success"
    assert result[0]["título"] == "Notícia de teste"
    assert result[0]["link"] == "https://example.com/news"
    assert [instance.proxy for instance in MockHttpClient.instances] == [None]


def test_connection_error_without_proxy_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connection error is returned as an audited error record."""
    MockHttpClient.error = ConnectionError("network unavailable")
    monkeypatch.setattr(httpx, "Client", MockHttpClient)

    result = make_client().search('"Marca" "fraude"')

    assert result[0]["status"] == "error"
    assert result[0]["status_http"] is None
    assert "network unavailable" in str(result[0]["erro"])


def test_connection_error_uses_proxy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A direct connection error retries successfully through the proxy."""
    MockHttpClient.error = ConnectionError("direct connection failed")
    MockHttpClient.response = httpx.Response(200, text=BING_HTML)
    monkeypatch.setattr(httpx, "Client", MockHttpClient)

    result = make_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

    assert result[0]["status"] == "success"
    assert [instance.proxy for instance in MockHttpClient.instances] == [
        None,
        "http://proxy.test:80",
    ]


def test_proxy_connection_error_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A direct and proxy connection failure is reported without network access."""
    MockHttpClient.error = ConnectionError("proxy connection failed")
    MockHttpClient.fail_for_proxy = True
    monkeypatch.setattr(httpx, "Client", MockHttpClient)

    result = make_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

    assert result[0]["status"] == "error"
    assert "proxy connection failed" in str(result[0]["erro"])
    assert [instance.proxy for instance in MockHttpClient.instances] == [
        None,
        "http://proxy.test:80",
    ]


def test_bing_parser_deduplicates_urls() -> None:
    """The Bing parser returns only one record for duplicate links."""
    duplicated_html = BING_HTML + BING_HTML

    result = parse_articles(duplicated_html, 10, datetime(2026, 9, 10))

    assert len(result) == 1
    assert result[0]["data_publicação"] == "2026-08-20"


def test_google_parser_returns_portuguese_fields() -> None:
    """The Google parser follows the same normalized output contract."""
    result = parse_google_articles(GOOGLE_HTML, 1, datetime(2026, 9, 10))

    assert result[0]["título"] == "Notícia Google"
    assert result[0]["origem"] == "Fonte Google"
    assert result[0]["link"] == "https://news.google.com/articles/teste"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hoje", "2026-09-10"),
        ("ontem", "2026-09-09"),
        ("3 dias", "2026-09-07"),
        ("Wed, 09 Sep 2026 10:00:00 GMT", "2026-09-09"),
        ("data desconhecida", None),
        (None, None),
    ],
)
def test_parse_date_handles_supported_formats(value: str | None, expected: str | None) -> None:
    """Relative, RFC and invalid publication dates are normalized consistently."""
    assert parse_date(value, datetime(2026, 9, 10)) == expected


def test_parsers_return_no_articles_for_empty_html() -> None:
    """Empty provider responses produce no article records for the caller to audit."""
    reference = datetime(2026, 9, 10)

    assert parse_articles("", 10, reference) == []
    assert parse_google_articles("", 10, reference) == []
