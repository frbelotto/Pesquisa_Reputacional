"""Bing News request and HTML parsing helpers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag

from .base import NewsSearchEngine


class BingNewsClient(NewsSearchEngine):
    """Search Bing News and normalize its results."""

    source_name = "bing"

    def search(self, query: str) -> list[dict[str, object]]:
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
            return [self._outcome(query, collected, "error", error=error)]
        if response.status_code != 200:
            status = "blocked" if response.status_code in {401, 403, 429} else "error"
            return [self._outcome(query, collected, status, response.status_code, f"HTTP {response.status_code}")]
        articles = parse_articles(response.text, self.limit, collected)
        if not articles:
            return [self._outcome(query, collected, "no_results", response.status_code)]
        return [self._outcome(query, collected, "success", response.status_code, article=article) for article in articles]


def text(card: Tag, selectors: tuple[str, ...]) -> str | None:
    """Return the first non-empty text matching the selectors."""
    for selector in selectors:
        node = card.select_one(selector)
        if node and (value := node.get_text(" ", strip=True)):
            return value
    return None


def parse_articles(html: str, limit: int, reference: datetime) -> list[dict[str, object]]:
    """Parse common Bing News card layouts and deduplicate URLs."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.news-card, div.t_s, article, a.title")
    results: list[dict[str, object]] = []
    seen: set[str] = set()
    for card in cards:
        anchor = card if card.name == "a" else card.select_one("a.title, a[href*='http'], a[href^='/news']")
        if not anchor or not anchor.get("href"):
            continue
        title = text(card, ("a.title", "a[class*='title']")) or (anchor.get_text(" ", strip=True) if card.name == "a" else None)
        if not title:
            continue
        url = str(anchor["href"])
        if url.startswith("/"):
            url = "https://www.bing.com" + url
        if url in seen:
            continue
        seen.add(url)
        published_text = text(card, ("span[class*='time']", "div[class*='time']", "span.algoSlug"))
        results.append({
            "título": title,
            "resumo": text(card, ("div.snippet", "p.snippet", "div[class*='snippet']")),
            "origem": text(card, ("div.source", "span.source", "div[class*='provider']")),
            "data_texto": published_text,
            "data_publicação": parse_date(published_text, reference),
            "link": url,
        })
        if len(results) >= limit:
            break
    return results


def parse_date(value: str | None, reference: datetime) -> str | None:
    """Parse Bing relative dates and standard email dates."""
    if not value:
        return None
    lowered = value.casefold()
    if "hoje" in lowered or "agora" in lowered:
        return reference.date().isoformat()
    if "ontem" in lowered:
        return (reference - timedelta(days=1)).date().isoformat()
    match = re.search(r"(?P<number>\d+)\s*(?P<unit>d|dia|dias|day|days)\b", lowered)
    if match:
        return (reference - timedelta(days=int(match.group("number")))).date().isoformat()
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return None
