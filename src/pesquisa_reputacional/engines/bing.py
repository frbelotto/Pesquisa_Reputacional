"""Bing News request and HTML parsing helpers."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin, urlencode, urlparse

from bs4 import BeautifulSoup, Tag

from ..model import NewsRecord
from .base import NewsSearchEngine
from .parsing import parse_date, text


class BingNewsClient(NewsSearchEngine):
    """Search Bing News and normalize its results."""

    source_name = "bing"

    def search(self, query: str) -> list[NewsRecord]:
        """Search Bing News and return articles or one audited outcome."""
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


def parse_articles(html: str, limit: int, reference: datetime) -> list[NewsRecord]:
    """Parse common Bing News card layouts and deduplicate URLs."""
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
        published_text = text(card, ("span[class*='time']", "div[class*='time']", "span.algoSlug"))
        results.append(NewsRecord.model_validate({
            "title": title,
            "summary": text(card, ("div.snippet", "p.snippet", "div[class*='snippet']")),
            "origin": text(card, ("div.source", "span.source", "div[class*='provider']")),
            "publication_text": published_text,
            "publication_date": parse_date(published_text, reference),
            "link": url,
        }))
        if len(results) >= limit:
            break
    return results


def _article_anchor(card: Tag) -> Tag | None:
    """Find an external article link instead of Bing's internal search link."""
    anchors = [card] if card.name == "a" else card.select("a[href]")
    external = [anchor for anchor in anchors if not _is_bing_search_url(str(anchor["href"]))]
    if external:
        return external[0]

    title_anchor = card.select_one("a.title")
    if title_anchor and title_anchor.get("href"):
        return title_anchor
    return None


def _is_bing_search_url(url: str) -> bool:
    """Return whether a URL points to a Bing News search result."""
    parsed = urlparse(urljoin("https://www.bing.com", url))
    hostname = (parsed.hostname or "").casefold()
    return hostname.endswith("bing.com") and parsed.path.rstrip("/") == "/news/search"
