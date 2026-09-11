"""Durable JSONL cache used to resume interrupted collections."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .engines.base import NewsSearchEngine

LOGGER = logging.getLogger(__name__)


def cache_key(query: str, client: NewsSearchEngine) -> str:
    """Create a stable key for one query and its relevant search settings."""
    value = f"{client.source_name}|{client.days}|{client.limit}|{query}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_cache(path: Path, max_age_days: int) -> dict[str, list[dict[str, object]]]:
    """Load valid JSONL cache entries and ignore an incomplete final line."""
    if not path.is_file():
        return {}

    cache_age = datetime.now(timezone.utc) - datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    )
    if cache_age > timedelta(days=max_age_days):
        path.unlink()
        LOGGER.info("Expired cache removed: %s", path)
        return {}

    cached: dict[str, list[dict[str, object]]] = {}
    with path.open("r", encoding="utf-8") as cache_file:
        for line in cache_file:
            try:
                entry = json.loads(line)
                if (
                    isinstance(entry, dict)
                    and isinstance(entry.get("chave"), str)
                    and isinstance(entry.get("registros"), list)
                ):
                    cached[entry["chave"]] = entry["registros"]
            except json.JSONDecodeError:
                LOGGER.warning("Ignoring an incomplete cache line in %s", path)
    return cached


def append_cache(path: Path, key: str, records: list[dict[str, object]]) -> None:
    """Persist one completed query from the collection coordinator thread."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as cache_file:
        json.dump({"chave": key, "registros": records}, cache_file, ensure_ascii=False)
        cache_file.write("\n")
        cache_file.flush()
        os.fsync(cache_file.fileno())


def remove_cache(path: Path | None) -> None:
    """Remove the recovery cache after the final report is safely written."""
    if path and path.is_file():
        path.unlink()