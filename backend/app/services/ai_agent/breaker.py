"""Cortacircuito del agente, compartido entre workers (B1).

El estado vive en PostgreSQL (``ai_breaker``) para que los dos workers de
uvicorn coincidan y sobreviva a reinicios. Se abre tras N fallos consecutivos
de red/protocolo y evita martillar un ESP32 caído.
"""

from __future__ import annotations

import math
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.ai import AiBreaker
from app.services.ai_agent.client import AgentCircuitOpenError
from app.utils.time import ensure_utc, utcnow

ROW_ID = 1


def _row(db: Session) -> AiBreaker:
    row = db.get(AiBreaker, ROW_ID)
    if row is None:
        row = AiBreaker(id=ROW_ID, failures=0, updated_at=utcnow())
        db.add(row)
    return row


def ensure_closed() -> None:
    """Falla con ``AgentCircuitOpenError`` mientras el cortacircuito esté abierto."""
    with SessionLocal() as db:
        row = db.get(AiBreaker, ROW_ID)
        if row is None or row.opened_until is None:
            return
        opened_until = ensure_utc(row.opened_until)
        now = utcnow()
        if opened_until is None or opened_until <= now:
            row.opened_until = None
            row.failures = 0
            db.add(row)
            db.commit()
            return
        retry_after = max(1, math.ceil((opened_until - now).total_seconds()))
        raise AgentCircuitOpenError(
            "El agente no está disponible; se reintentará automáticamente",
            retry_after=retry_after,
        )


def record_failure() -> None:
    """Suma un fallo y abre el cortacircuito al alcanzar el umbral."""
    threshold = settings.ai_agent_breaker_failures
    if threshold <= 0:
        return
    with SessionLocal() as db:
        row = _row(db)
        row.failures += 1
        row.updated_at = utcnow()
        if row.failures >= threshold:
            row.opened_until = utcnow() + timedelta(
                seconds=max(1, settings.ai_agent_breaker_seconds)
            )
            row.failures = 0
        db.add(row)
        db.commit()


def record_success() -> None:
    """Limpia los fallos acumulados tras una respuesta correcta."""
    with SessionLocal() as db:
        row = db.get(AiBreaker, ROW_ID)
        if row is None or (row.failures == 0 and row.opened_until is None):
            return
        row.failures = 0
        row.opened_until = None
        row.updated_at = utcnow()
        db.add(row)
        db.commit()


def reset() -> None:
    """Reinicia el estado (pruebas y diagnóstico)."""
    with SessionLocal() as db:
        row = db.get(AiBreaker, ROW_ID)
        if row is not None:
            db.delete(row)
            db.commit()
