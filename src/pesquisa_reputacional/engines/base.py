"""Common contract and HTTP behavior for news search engines."""

from __future__ import annotations

import logging
import random
import threading
import time
from abc import ABC, abstractmethod

import httpx2 as httpx

from ..model import NewsRecord

LOGGER = logging.getLogger(__name__)


class NewsSearchEngine(ABC):
    """Contract implemented by every supported news search engine."""

    source_name: str

    def __init__(self, *, limit: int, days: int, concurrency: int, delay: float, timeout: float, retries: int, proxy: str | None) -> None:
        self.limit = limit
        self.days = days
        self.concurrency = concurrency
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.proxy = proxy
        self._lock = threading.Lock()
        self._last_request = 0.0

    @abstractmethod
    def search(self, query: str) -> list[NewsRecord]:
        """Search the engine and return normalized article records."""

    def _request(self, url: str) -> tuple[httpx.Response | None, str | None]:
        """Request a URL with retries and an optional proxy fallback."""
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
        }

        def request(proxy: str | None) -> tuple[httpx.Response | None, str | None]:
            """Execute one direct or proxy request with the configured retries."""
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

        LOGGER.warning("Direct %s request failed; trying proxy fallback", self.source_name)
        response, error = request(self.proxy)
        if response is not None:
            LOGGER.info("%s request succeeded using fallback proxy", self.source_name)
        return response, error

    def _client(self, proxy: str | None) -> httpx.Client:
        """Create an HTTPX2 client while keeping proxy setup in one place."""
        if proxy:
            return httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                trust_env=False,
                mounts={
                    "all://": httpx.HTTPTransport(proxy=proxy),
                },
            )
        return httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            trust_env=False,
        )

    def _wait(self) -> None:
        """Enforce the configured delay between requests."""
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
        """Create a normalized result for success, empty, or failed searches."""
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
