"""Google News request and HTML parsing helpers."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..model import NewsRecord
from .base import NewsSearchEngine
from .parsing import parse_date, text


class GoogleNewsClient(NewsSearchEngine):
    """Search Google News and normalize its results."""

    source_name = "google"

    def search(self, query: str) -> list[NewsRecord]:
        """Search Google News and return articles or one audited outcome."""
        url = "https://news.google.com/search?" + urlencode({
            "q": query,
            "when": f"{self.days}d",
            "hl": "pt-BR",
            "gl": "BR",
            "ceid": "BR:pt-419",
        })
        response, error = self._request(url)
        collected = datetime.now().astimezone()
        if response is None:
            return [self._outcome("error", error=error)]
        if response.status_code != 200:
            status = "blocked" if response.status_code in {401, 403, 429} else "error"
            return [self._outcome(status, response.status_code, f"HTTP {response.status_code}")]
        articles = parse_google_articles(response.text, self.limit, collected)
        if not articles:
            return [self._outcome("no_results", response.status_code)]
        return [
            self._outcome("success", response.status_code, article=article)
            for article in articles
        ]


def parse_google_articles(html: str, limit: int, reference: datetime) -> list[NewsRecord]:
    """Parse the common Google News article layout and deduplicate URLs."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[NewsRecord] = []
    seen: set[str] = set()
    for card in soup.select("article"):
        title = text(card, ("h3", "h4", "a[class*='title']"))
        anchor = card.select_one("h3 a, h4 a, a[href^='./articles/'], a[href^='/articles/']")
        if not title or not anchor or not anchor.get("href"):
            continue
        url = str(anchor["href"])
        if url.startswith("./"):
            url = "https://news.google.com/" + url[2:]
        elif url.startswith("/"):
            url = "https://news.google.com" + url
        if url in seen:
            continue
        seen.add(url)
        published_text = text(card, ("time", "div[data-time]", "span[class*='time']"))
        results.append(NewsRecord.model_validate({
            "title": title,
            "summary": text(card, ("p", "div[class*='snippet']")),
            "origin": text(card, ("div[data-n-tid]", "a[data-n-tid]", "div[class*='source']")),
            "publication_text": published_text,
            "publication_date": parse_date(published_text, reference),
            "link": url,
        }))
        if len(results) >= limit:
            break
    return results
