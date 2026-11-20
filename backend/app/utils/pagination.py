"""Cursores opacos para paginación keyset."""

from __future__ import annotations

import base64
from datetime import datetime

from app.utils.time import ensure_utc


def encode_cursor(timestamp: datetime, item_id: int) -> str:
    raw = f"{timestamp.isoformat()}|{item_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int] | None:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        timestamp_raw, item_id_raw = raw.rsplit("|", 1)
        parsed = ensure_utc(datetime.fromisoformat(timestamp_raw))
        if parsed is None:
            return None
        return parsed, int(item_id_raw)
    except (ValueError, UnicodeDecodeError, TypeError):
        return None
