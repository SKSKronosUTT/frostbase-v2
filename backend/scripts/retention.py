"""Retención de lecturas y alertas resueltas (T4.9).

Uso:
    python -m scripts.retention --dry-run
    python -m scripts.retention --readings-days 90 --alerts-days 365

El job es idempotente: si no hay filas antiguas no elimina nada. Se ejecuta
también desde el servicio ``watcher`` cada ``RETENTION_CHECK_SECONDS``.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.reading import Reading
from app.utils.time import utcnow

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("frostbase.retention")


@dataclass
class RetentionResult:
    readings: int
    alerts: int
    dry_run: bool

    def summary(self) -> str:
        prefix = "Simulación" if self.dry_run else "Retención aplicada"
        return f"{prefix}: {self.readings} lecturas y {self.alerts} alertas"


def _cutoff(days: int):
    return utcnow() - timedelta(days=max(1, days))


def run_retention(
    db: Session,
    *,
    readings_days: int | None = None,
    alerts_days: int | None = None,
    dry_run: bool = False,
) -> RetentionResult:
    readings_limit = _cutoff(readings_days or settings.readings_retention_days)
    alerts_limit = _cutoff(alerts_days or settings.resolved_alerts_retention_days)

    readings_filter = Reading.received_at < readings_limit
    alerts_filter = (
        (Alert.status == "resuelta")
        & (Alert.resolved_at.is_not(None))
        & (Alert.resolved_at < alerts_limit)
    )

    if dry_run:
        readings = db.scalar(select(func.count(Reading.id)).where(readings_filter)) or 0
        alerts = db.scalar(select(func.count(Alert.id)).where(alerts_filter)) or 0
        return RetentionResult(readings=readings, alerts=alerts, dry_run=True)

    readings_result = db.execute(delete(Reading).where(readings_filter))
    alerts_result = db.execute(delete(Alert).where(alerts_filter))
    result = RetentionResult(
        readings=getattr(readings_result, "rowcount", 0) or 0,
        alerts=getattr(alerts_result, "rowcount", 0) or 0,
        dry_run=False,
    )
    db.commit()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Retención de datos de FrostBase")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--readings-days", type=int, default=None)
    parser.add_argument("--alerts-days", type=int, default=None)
    args = parser.parse_args()

    with SessionLocal() as db:
        result = run_retention(
            db,
            readings_days=args.readings_days,
            alerts_days=args.alerts_days,
            dry_run=args.dry_run,
        )
    logger.info(result.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
