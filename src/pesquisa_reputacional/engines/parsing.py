"""Parsing helpers shared by the news engine implementations."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from bs4 import Tag


def text(card: Tag, selectors: tuple[str, ...]) -> str | None:
    """Return the first non-empty text matching the selectors."""
    for selector in selectors:
        node = card.select_one(selector)
        if node and (value := node.get_text(" ", strip=True)):
            return value
    return None


def parse_date(value: str | None, reference: datetime) -> str | None:
    """Parse relative dates and standard email dates used by news pages."""
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