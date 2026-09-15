"""Unit tests for the Google News engine."""

from datetime import datetime
from typing import Any

import httpx2 as httpx
import pytest

from pesquisa_reputacional.engines.google import GoogleNewsClient, parse_google_articles


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
    """Reset Google HTTP mock state between tests."""
    MockHttpClient.instances = []
    MockHttpClient.response = None
    MockHttpClient.error = None
    MockHttpClient.fail_for_proxy = False


def make_google_client(proxy: str | None = None, retries: int = 0) -> GoogleNewsClient:
    """Create a Google client with fast settings for unit tests."""
    return GoogleNewsClient(
        limit=1,
        days=60,
        concurrency=1,
        delay=0,
        timeout=1,
        retries=retries,
        proxy=proxy,
    )


class TestGoogleEngine:
    """Tests for GoogleNewsClient and Google-specific parsing."""

    def test_search_uses_mocked_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A successful mocked Google response becomes a normalized article."""
        MockHttpClient.response = httpx.Response(200, text=GOOGLE_HTML)
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_google_client().search('"Marca" "fraude"')

        assert result[0].status == "success"
        assert result[0].title == "Notícia Google"
        assert result[0].link == "https://news.google.com/articles/teste"
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [False]

    def test_connection_error_without_proxy_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Google connection error is returned as an audited error record."""
        MockHttpClient.error = ConnectionError("network unavailable")
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_google_client().search('"Marca" "fraude"')

        assert result[0].status == "error"
        assert result[0].http_status is None
        assert "network unavailable" in str(result[0].error)

    def test_connection_error_uses_proxy_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Google direct connection error retries through the proxy."""
        MockHttpClient.error = ConnectionError("direct connection failed")
        MockHttpClient.response = httpx.Response(200, text=GOOGLE_HTML)
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_google_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

        assert result[0].status == "success"
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [
            False,
            True,
        ]

    def test_proxy_connection_error_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A Google direct and proxy failure is reported without network access."""
        MockHttpClient.error = ConnectionError("proxy connection failed")
        MockHttpClient.fail_for_proxy = True
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_google_client(proxy="http://proxy.test:80").search('"Marca" "fraude"')

        assert result[0].status == "error"
        assert "proxy connection failed" in str(result[0].error)
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [
            False,
            True,
        ]

    def test_parser_returns_portuguese_fields(self) -> None:
        """The Google parser follows the normalized output contract."""
        result = parse_google_articles(GOOGLE_HTML, 1, datetime(2026, 9, 10))

        assert result[0].title == "Notícia Google"
        assert result[0].origin == "Fonte Google"
        assert result[0].link == "https://news.google.com/articles/teste"

    def test_parser_deduplicates_urls(self) -> None:
        """The Google parser returns only one record for duplicate links."""
        result = parse_google_articles(
            GOOGLE_HTML + GOOGLE_HTML,
            10,
            datetime(2026, 9, 10),
        )

        assert len(result) == 1
        assert result[0].link == "https://news.google.com/articles/teste"

    def test_parser_returns_no_articles_for_empty_html(self) -> None:
        """The Google parser returns no articles for empty HTML."""
        result = parse_google_articles("", 10, datetime(2026, 9, 10))

        assert result == []
