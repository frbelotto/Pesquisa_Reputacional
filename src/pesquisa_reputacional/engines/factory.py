"""Factory for registered news search engines."""

from __future__ import annotations

from .base import NewsSearchEngine


def create_engine(name: str, **kwargs: object) -> NewsSearchEngine:
    """Create a concrete engine from its configuration name."""
    if name == "bing":
        from .bing import BingNewsClient

        return BingNewsClient(**kwargs)
    if name == "google":
        from .google import GoogleNewsClient

        return GoogleNewsClient(**kwargs)
    raise ValueError(f"Unsupported news engine: {name}")
