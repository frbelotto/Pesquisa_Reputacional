"""Testes unitários do cliente Bing News."""

from datetime import datetime
from typing import Any

import httpx2 as httpx
import pytest

from pesquisa_reputacional.engines.bing import BingNewsClient, parse_articles, parse_date


BING_HTML = """
<div class="news-card">
  <a class="title" href="https://example.com/news">Notícia de teste</a>
  <div class="snippet">Resumo da notícia</div>
  <div class="source">Fonte de teste</div>
  <span class="time">21d</span>
</div>
"""


class MockHttpClient:
    """Gerenciador de contexto que simula requisições diretas e via proxy."""

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
    """Reinicia o estado do mock HTTP do Bing entre os testes."""
    MockHttpClient.instances = []
    MockHttpClient.response = None
    MockHttpClient.error = None
    MockHttpClient.fail_for_proxy = False


def make_bing_client(proxy: str | None = None, retries: int = 0) -> BingNewsClient:
    """Cria um cliente Bing com configurações rápidas para os testes."""
    return BingNewsClient(
        limit=1,
        days=60,
        delay=0,
        timeout=1,
        retries=retries,
        proxy=proxy,
    )


class TestBingEngine:
    """Testes do BingNewsClient e do parser específico do Bing."""

    def test_search_uses_mocked_connection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Uma resposta simulada bem-sucedida vira um artigo normalizado."""
        MockHttpClient.response = httpx.Response(200, text=BING_HTML)
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client().search('"Marca" "fraude"')

        assert result[0].status == "success"
        assert result[0].title == "Notícia de teste"
        assert result[0].link == "https://example.com/news"
        assert [instance.uses_proxy for instance in MockHttpClient.instances] == [False]

    def test_connection_error_without_proxy_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Um erro de conexão do Bing retorna um registro de erro auditável."""
        MockHttpClient.error = ConnectionError("network unavailable")
        monkeypatch.setattr(httpx, "Client", MockHttpClient)

        result = make_bing_client().search('"Marca" "fraude"')

        assert result[0].status == "error"
        assert result[0].http_status is None
        assert "network unavailable" in str(result[0].error)

    def test_connection_error_uses_proxy_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Um erro de conexão direta do Bing tenta novamente pelo proxy."""
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
        """Falhas na conexão direta e no proxy são reportadas sem acesso real à rede."""
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
        """O parser do Bing retorna apenas um registro para links duplicados."""
        duplicated_html = BING_HTML + BING_HTML

        result = parse_articles(duplicated_html, 10, datetime(2026, 9, 10))

        assert len(result) == 1
        assert result[0].publication_date == "2026-08-20"

    def test_parser_prefers_article_url_over_bing_search_url(self) -> None:
        """O parser ignora links de busca do Bing dentro de um card de notícia."""
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
        """O parser do Bing não retorna artigos para HTML vazio."""
        result = parse_articles("", 10, datetime(2026, 9, 10))

        assert result == []

    def test_parser_extracts_relative_date_from_origin(self) -> None:
        """Alguns layouts do Bing acrescentam a idade relativa ao nome do veículo."""
        html = """
        <div class="news-card">
          <a class="title" href="https://example.com/article">Notícia</a>
          <div class="source">InfoMoney 14a</div>
        </div>
        """

        result = parse_articles(html, 10, datetime(2026, 9, 10))

        assert result[0].origin == "InfoMoney"
        assert result[0].publication_text == "14a"
        assert result[0].publication_date == "2012-09-13"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1mês(es)", "2026-08-11"),
            ("3dia(s)", "2026-09-07"),
            ("2 horas", "2026-09-09"),
            ("90 min", "2026-09-09"),
        ],
    )
    def test_parse_date_accepts_bing_relative_suffixes(
        self, value: str, expected: str
    ) -> None:
        reference = datetime(2026, 9, 10, 1, 0)
        assert parse_date(value, reference) == expected

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
    def test_parse_date(self, value: str | None, expected: str | None) -> None:
        """O texto de data do Bing é normalizado para o relatório."""
        assert parse_date(value, datetime(2026, 9, 10)) == expected
