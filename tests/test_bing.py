"""Unit tests for the Bing News engine."""

from datetime import datetime
from typing import Any

import httpx2 as httpx
import pytest

from pesquisa_reputacional.engines.bing import BingNewsClient, parse_articles


BING_HTML = """
<div class="news-card">
  <a class="title" href="https://example.com/news">Notícia de teste</a>
  <div class="snippet">Resumo da notícia</div>
  <div class="source">Fonte de teste</div>
  <span class="time">21d</span>
</div>
"""


class MockHttpClient:
    """Context manager that simulates direct and proxy HTTP requests."""

    instances: list["MockHttpClient"] = []
    response: httpx.Response | None = None
    error: Exception | None = None
    fail_for_proxy = False

    def __init__(self, **kwargs: Any) -> None:
        self.uses_proxy = bool(kwargs.get("mounts"))
        type(self).instances.append(self)

    def __enter__(self) -> "MockHttpClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def get(self, url: str, **_kwargs: Any) -> httpx.Response:
        if self.error is not None and (not self.uses_proxy or self.fail_for_proxy):
            request = httpx.Request("GET", url)
            raise httpx.ConnectError(str(self.error), request=request)
        if self.response is None:
            raise AssertionError("Mock response was not configured")
        return self.response


@pytest.fixture(autouse=True)
def reset_http_mock() -> None:
    """Reset Bing HTTP mock state between tests."""
    MockHttpClient.instances = []
    MockHttpClient.response = None
    MockHttpClient.error = None
    MockHttpClient.fail_for_proxy = False


def make_bing_client(proxy: str | None = None, retries: int = 0) -> BingNewsClient:
    """Create a Bing client with fast settings for unit tests."""
    return BingNewsClient(
        limit=1,
        days=60,
        concurrency=1,
        delay=0,
        timeout=1,
        retries=retries,
        proxy=proxy,
    )


class TestBingEngine:
    """Tests for BingNewsClient and Bing-specific parsing."""

    def test_search_uses_mocked_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A successful mocked Bing response becomes a normalized article."""
        MockHttpClient.response = httpx.Response(200, text=BING_HTML)
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client().search('"Marca" "fraude"')

        assert result[0].status == "success"
        assert result[0].title == "Notícia de teste"
        assert result[0].link == "https://example.com/news"
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [False]

    def test_connection_error_without_proxy_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Bing connection error is returned as an audited error record."""
        MockHttpClient.error = ConnectionError("network unavailable")
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client().search('"Marca" "fraude"')

        assert result[0].status == "error"
        assert result[0].http_status is None
        assert "network unavailable" in str(result[0].error)

    def test_connection_error_uses_proxy_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Bing direct connection error retries through the proxy."""
        MockHttpClient.error = ConnectionError("direct connection failed")
        MockHttpClient.response = httpx.Response(200, text=BING_HTML)
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

        assert result[0].status == "success"
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [
            False,
            True,
        ]

    def test_proxy_connection_error_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Bing direct and proxy failure is reported without network access."""
        MockHttpClient.error = ConnectionError("proxy connection failed")
        MockHttpClient.fail_for_proxy = True
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

        assert result[0].status == "error"
        assert "proxy connection failed" in str(result[0].error)
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [
            False,
            True,
        ]

    def test_parser_deduplicates_urls(self) -> None:
        """The Bing parser returns only one record for duplicate links."""
        duplicated_html = BING_HTML + BING_HTML

        result = parse_articles(duplicated_html, 10, datetime(2026, 9, 10))

        assert len(result) == 1
        assert result[0].publication_date == "2026-08-20"

        def test_parser_prefers_article_url_over_bing_search_url(self) -> None:
                """The parser ignores Bing search links embedded in a news card."""
                html = """
                <div class="news-card">
                    <a class="title" href="https://www.bing.com/news/search?q=site%3Aexample.com">
                        Notícia de teste
                    </a>
                    <a href="https://example.com/article">Notícia de teste</a>
                    <span class="time">hoje</span>
                </div>
                """

                result = parse_articles(html, 10, datetime(2026, 9, 10))

                assert result[0].link == "https://example.com/article"

    def test_parser_returns_no_articles_for_empty_html(self) -> None:
        """The Bing parser returns no articles for empty HTML."""
        result = parse_articles("", 10, datetime(2026, 9, 10))

        assert result == []
