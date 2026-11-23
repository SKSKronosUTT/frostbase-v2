"""Cuota diaria del asistente, atómica entre workers (PostgreSQL)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.ai import AiUsage


class QuotaExceededError(Exception):
    pass


def consume(db: Session, *, admin_id: int, day: date, limit: int) -> int:
    """Incrementa el contador del día y devuelve el valor; falla si se agotó.

    El ``WHERE`` del UPSERT evita superar el límite incluso con peticiones
    concurrentes; si no devuelve fila, el límite ya estaba alcanzado.
    """
    statement = (
        pg_insert(AiUsage)
        .values(admin_id=admin_id, day=day, count=1)
        .on_conflict_do_update(
            index_elements=["admin_id", "day"],
            set_={"count": AiUsage.count + 1},
            where=AiUsage.count < limit,
        )
        .returning(AiUsage.count)
    )
    value = db.scalar(statement)
    if value is None:
        raise QuotaExceededError(
            f"Se alcanzó el límite diario de {limit} consultas al asistente"
        )
    db.flush()
    return int(value)
