"""Unit tests for parsing helpers shared by news engines."""

from datetime import datetime

import pytest

from pesquisa_reputacional.engines.parsing import parse_date


class TestSharedParsing:
    """Tests for helpers shared by the Bing and Google parsers."""

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
    def test_parse_date_handles_supported_formats(
        self, value: str | None, expected: str | None
    ) -> None:
        """Relative, RFC and invalid dates are normalized consistently."""
        assert parse_date(value, datetime(2026, 9, 10)) == expected
