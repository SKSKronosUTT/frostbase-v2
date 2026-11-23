"""Lock distribuido del agente: una sola petición concurrente entre workers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text

from app.core.database import engine
from app.services.ai_agent.client import AgentBusyError

LOCK_KEY = 7712028


@contextmanager
def agent_lock() -> Iterator[None]:
    """Adquiere un advisory lock de PostgreSQL o falla con ``AgentBusyError``.

    Se usa una conexión dedicada porque el lock es de sesión; se libera siempre
    en el ``finally``. Al ser compartido por todos los workers, garantiza que
    solo una conversación usa el ESP32 a la vez.
    """
    connection = engine.connect()
    try:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
            ).scalar()
        )
        if not acquired:
            raise AgentBusyError(
                "El asistente está atendiendo otra consulta; intente en unos segundos"
            )
        try:
            yield
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}
            )
    finally:
        connection.close()
