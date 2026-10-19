"""Funções auxiliares para requisições e leitura do HTML do Bing News."""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlencode, urlparse

import httpx2 as httpx
from bs4 import BeautifulSoup, Tag

from ..model import NewsRecord

LOGGER = logging.getLogger(__name__)
SOURCE_NAME = "bing"
RELATIVE_DATE_PATTERN = re.compile(
    r"(?P<number>\d+)\s*(?P<unit>"
    r"a(?:no)?(?:s|\(s\))?\.??|"
    r"m(?:ê|e)s(?:\(es\))?\.??|"
    r"semana[s]?|"
    r"d(?:ia)?(?:s|\(s\))?|"
    r"h(?:ora[s]?)?|"
    r"min(?:uto[s]?)?"
    r")(?!\w)",
    re.IGNORECASE,
)


def text(card: Tag, selectors: tuple[str, ...]) -> str | None:
    """Retorna o primeiro texto não vazio que corresponda aos seletores."""
    for selector in selectors:
        node = card.select_one(selector)
        if node and (value := node.get_text(" ", strip=True)):
            return value
    return None


def parse_date(value: str | None, reference: datetime) -> str | None:
    """Interpreta datas relativas e datas padrão usadas pelo Bing."""
    if not value:
        return None
    lowered = value.casefold()
    if "hoje" in lowered or "agora" in lowered:
        return reference.date().isoformat()
    if "ontem" in lowered:
        return (reference - timedelta(days=1)).date().isoformat()
    match = RELATIVE_DATE_PATTERN.search(lowered)
    if match:
        number = int(match.group("number"))
        unit = match.group("unit").casefold()
        if unit.startswith("a"):
            days = number * 365
        elif unit.startswith(("mê", "me")):
            days = number * 30
        elif unit.startswith("semana"):
            days = number * 7
        elif unit.startswith("h"):
            return (reference - timedelta(hours=number)).date().isoformat()
        elif unit.startswith("min"):
            return (reference - timedelta(minutes=number)).date().isoformat()
        else:
            days = number
        return (reference - timedelta(days=days)).date().isoformat()
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None


class BingNewsClient:
    """Pesquisa no Bing News e normaliza os resultados."""

    source_name = SOURCE_NAME

    def __init__(
        self,
        *,
        limit: int,
        days: int,
        delay: float,
        timeout: float,
        retries: int,
        proxy: str | None,
    ) -> None:
        self.limit = limit
        self.days = days
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.proxy = proxy
        self._lock = threading.Lock()
        self._last_request = 0.0

    def search(self, query: str) -> list[NewsRecord]:
        """Pesquisa no Bing News e retorna artigos ou um resultado auditável."""
        url = "https://www.bing.com/news/search?" + urlencode({
            "q": query,
            "setlang": "pt-BR",
            "cc": "BR",
            "qft": f'interval="{self.days}"',
            "form": "QBNH",
        })
        response, error = self._request(url)
        collected = datetime.now().astimezone()
        if response is None:
            return [self._outcome("error", error=error)]
        if response.status_code != 200:
            status = "blocked" if response.status_code in {401, 403, 429} else "error"
            return [self._outcome(status, response.status_code, f"HTTP {response.status_code}")]
        articles = parse_articles(response.text, self.limit, collected)
        if not articles:
            return [self._outcome("no_results", response.status_code)]
        return [
            self._outcome("success", response.status_code, article=article)
            for article in articles
        ]

    def _request(self, url: str) -> tuple[httpx.Response | None, str | None]:
        """Acessa uma URL com tentativas adicionais e fallback opcional de proxy."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        }

        def request(proxy: str | None) -> tuple[httpx.Response | None, str | None]:
            last_error: str | None = None
            for attempt in range(self.retries + 1):
                self._wait()
                try:
                    with self._client(proxy) as client:
                        response = client.get(url, headers=headers)
                    if response.status_code in {500, 502, 503, 504} and attempt < self.retries:
                        time.sleep(2**attempt + random.random())
                        continue
                    return response, None
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                    if attempt < self.retries:
                        time.sleep(2**attempt + random.random())
            return None, last_error or "Unknown HTTP error"

        response, error = request(None)
        if response is not None or self.proxy is None:
            return response, error

        LOGGER.warning("Direct Bing request failed; trying proxy fallback")
        response, error = request(self.proxy)
        if response is not None:
            LOGGER.info("Bing request succeeded using fallback proxy")
        return response, error

    def _client(self, proxy: str | None) -> httpx.Client:
        """Cria um cliente HTTP para requisições diretas ou via proxy."""
        if proxy:
            return httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                trust_env=False,
                mounts={"all://": httpx.HTTPTransport(proxy=proxy)},
            )
        return httpx.Client(timeout=self.timeout, follow_redirects=True, trust_env=False)

    def _wait(self) -> None:
        """Aplica o atraso configurado entre as requisições."""
        with self._lock:
            remaining = self.delay - (time.monotonic() - self._last_request)
            if remaining > 0:
                time.sleep(remaining)
            self._last_request = time.monotonic()

    @staticmethod
    def _outcome(
        status: str,
        http_status: int | None = None,
        error: str | None = None,
        article: NewsRecord | None = None,
    ) -> NewsRecord:
        """Cria um resultado normalizado para pesquisas bem-sucedidas, vazias ou com falha."""
        if article is None:
            return NewsRecord.model_validate({
                "http_status": http_status,
                "status": status,
                "error": error,
            })
        return article.model_copy(update={
            "http_status": http_status,
            "status": status,
            "error": error,
        })


def parse_articles(html: str, limit: int, reference: datetime) -> list[NewsRecord]:
    """Interpreta layouts comuns de cards do Bing News e remove URLs duplicadas."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.news-card, div.t_s, article, a.title")
    results: list[NewsRecord] = []
    seen: set[str] = set()
    for card in cards:
        anchor = _article_anchor(card)
        if not anchor or not anchor.get("href"):
            continue
        title = text(card, ("a.title", "a[class*='title']")) or (anchor.get_text(" ", strip=True) if card.name == "a" else None)
        if not title:
            continue
        url = urljoin("https://www.bing.com", str(anchor["href"]))
        if url in seen:
            continue
        seen.add(url)
        origin = text(card, (
            "div.source",
            "span.source",
            "div[class*='provider']",
        ))
        published_text = text(card, (
            "time",
            "span[class*='time']",
            "div[class*='time']",
            "span.algoSlug",
            "div.source span",
            "div[class*='provider'] span",
        ))
        if not published_text and origin:
            date_match = RELATIVE_DATE_PATTERN.search(origin)
            if date_match:
                published_text = date_match.group(0)
                origin = origin[:date_match.start()].strip(" -|\u00a0") or None
        results.append(NewsRecord.model_validate({
            "title": title,
            "summary": text(card, ("div.snippet", "p.snippet", "div[class*='snippet']")),
            "origin": origin,
            "publication_text": published_text,
            "publication_date": parse_date(published_text, reference),
            "link": url,
        }))
        if len(results) >= limit:
            break
    return results


def _article_anchor(card: Tag) -> Tag | None:
    """Encontra o link externo da notícia em vez do link interno de busca do Bing."""
    anchors = [card] if card.name == "a" else card.select("a[href]")
    external = [anchor for anchor in anchors if not _is_bing_search_url(str(anchor["href"]))]
    if external:
        return external[0]

    title_anchor = card.select_one("a.title")
    if title_anchor and title_anchor.get("href"):
        return title_anchor
    return None


def _is_bing_search_url(url: str) -> bool:
    """Indica se uma URL aponta para um resultado de busca do Bing News."""
    parsed = urlparse(urljoin("https://www.bing.com", url))
    hostname = (parsed.hostname or "").casefold()
    return hostname.endswith("bing.com") and parsed.path.rstrip("/") == "/news/search"
