"""Auditoría y métricas del asistente (A5). Sin contenido del chat."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.ai import AiAudit
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.ai")


def record_event(
    *,
    admin_id: int | None,
    action: str,
    status: str,
    http_status: int | None = None,
    latency_ms: int | None = None,
    conversation_id: uuid.UUID | None = None,
    detail: str | None = None,
) -> None:
    """Registra un evento en una transacción propia.

    Se usa una sesión independiente para que la auditoría sobreviva aunque la
    petición del chat termine en error (y su transacción haga rollback).
    """
    try:
        with SessionLocal() as db:
            db.add(
                AiAudit(
                    admin_id=admin_id,
                    action=action,
                    status=status,
                    http_status=http_status,
                    latency_ms=latency_ms,
                    conversation_id=conversation_id,
                    detail=(detail or "")[:120] or None,
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001 - la auditoría nunca debe tumbar la petición
        logger.exception("No se pudo registrar la auditoría del asistente")


def metrics(db: Session, *, days: int = 7) -> dict:
    """Agrega en PostgreSQL para no cargar toda la auditoría en memoria."""
    since = utcnow() - timedelta(days=days)
    grouped = db.execute(
        select(
            AiAudit.action,
            AiAudit.status,
            AiAudit.http_status,
            func.count(AiAudit.id),
        )
        .where(AiAudit.created_at >= since)
        .group_by(AiAudit.action, AiAudit.status, AiAudit.http_status)
    ).all()

    requests = 0
    errors = 0
    by_action: dict[str, int] = {}
    errors_by_status: dict[str, int] = {}
    for action, status, http_status, count in grouped:
        requests += count
        by_action[action] = by_action.get(action, 0) + count
        if status != "ok":
            errors += count
            key = str(http_status or "error")
            errors_by_status[key] = errors_by_status.get(key, 0) + count

    latency = db.execute(
        select(
            func.count(AiAudit.latency_ms),
            func.avg(AiAudit.latency_ms),
            func.percentile_cont(0.50).within_group(AiAudit.latency_ms.asc()),
            func.percentile_cont(0.95).within_group(AiAudit.latency_ms.asc()),
        ).where(
            AiAudit.created_at >= since,
            AiAudit.latency_ms.is_not(None),
        )
    ).one()

    def _rounded(value) -> int | None:
        return int(round(float(value))) if value is not None else None

    return {
        "days": days,
        "generated_at": utcnow(),
        "requests": requests,
        "errors": errors,
        "by_action": by_action,
        "errors_by_http_status": errors_by_status,
        "latency_avg_ms": (
            round(float(latency[1]), 1) if latency[1] is not None else None
        ),
        "latency_p50_ms": _rounded(latency[2]),
        "latency_p95_ms": _rounded(latency[3]),
    }


def prune_old(db: Session) -> int:
    """Elimina auditoría más antigua que ``AI_AUDIT_RETENTION_DAYS``."""
    cutoff = utcnow() - timedelta(days=max(1, settings.ai_audit_retention_days))
    deleted = db.query(AiAudit).filter(AiAudit.created_at < cutoff).delete()
    db.flush()
    return int(deleted or 0)


def last_read_at(db: Session) -> datetime | None:
    """Último acceso del agente a ``agent-read`` (sin token ni contenido)."""
    value = db.scalar(
        select(func.max(AiAudit.created_at)).where(AiAudit.action == "read")
    )
    return value if isinstance(value, datetime) else None


def count_today(db: Session, *, admin_id: int) -> int:
    today = datetime.now(settings.tz).date()
    start = datetime.combine(today, datetime.min.time(), tzinfo=settings.tz)
    return int(
        db.scalar(
            select(func.count(AiAudit.id)).where(
                AiAudit.admin_id == admin_id,
                AiAudit.created_at >= start,
            )
        )
        or 0
    )
