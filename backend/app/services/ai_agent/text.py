"""Saneado común de texto devuelto por el agente."""

from __future__ import annotations

import re

# Caracteres de control C0 salvo tabulador (0x09) y saltos de línea (0x0a/0x0d).
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: str | None, *, limit: int) -> tuple[str, bool]:
    """Quita caracteres de control y recorta a ``limit`` caracteres.

    Devuelve ``(texto, truncado)``. Se usa tanto en las respuestas del chat
    como en el historial leído del agente.
    """
    cleaned = CONTROL_CHARS.sub("", text or "").strip()
    max_chars = max(1, limit)
    return cleaned[:max_chars], len(cleaned) > max_chars
