from datetime import UTC, datetime

from app.utils.pagination import decode_cursor, encode_cursor
from app.utils.search import escape_like


def test_cursor_round_trip():
    timestamp = datetime(2026, 11, 20, 12, 30, tzinfo=UTC)
    cursor = encode_cursor(timestamp, 42)
    decoded = decode_cursor(cursor)
    assert decoded is not None
    assert decoded[0] == timestamp
    assert decoded[1] == 42


def test_invalid_cursor_returns_none():
    assert decode_cursor("no-es-un-cursor") is None
    assert decode_cursor("") is None


def test_escape_like():
    assert escape_like("100%_test") == "100\\%\\_test"
    assert escape_like("a\\b") == "a\\\\b"
