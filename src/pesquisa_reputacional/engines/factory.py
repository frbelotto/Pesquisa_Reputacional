"""Registry for the available news search engine implementations."""

from __future__ import annotations

from typing import Any

from .base import NewsSearchEngine
from .bing import BingNewsClient
from .google import GoogleNewsClient

ENGINE_REGISTRY: dict[str, type[NewsSearchEngine]] = {
    "bing": BingNewsClient,
    "google": GoogleNewsClient,
}


def create_engine(name: str, **kwargs: Any) -> NewsSearchEngine:
    """Create a registered engine from its configuration name."""
    try:
        engine_type = ENGINE_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported news engine: {name}") from exc
    return engine_type(**kwargs)
