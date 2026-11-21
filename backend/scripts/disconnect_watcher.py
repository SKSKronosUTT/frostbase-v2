"""Servicio de vigilancia de desconexiones y retención (fuera del proceso web).

Ejecuta el ciclo set-based de ``alert_service.check_disconnected_devices`` cada
``DISCONNECT_CHECK_SECONDS`` y la retención de datos cada
``RETENTION_CHECK_SECONDS``. Un advisory lock de PostgreSQL garantiza que solo
una instancia trabaje aunque haya varias réplicas.

Uso en contenedor:
    python -m scripts.disconnect_watcher
"""

from __future__ import annotations

import logging
import signal
import time

from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.services import alert_service, settings_service
from scripts.retention import run_retention

LOCK_KEY = 7712027
logger = logging.getLogger("frostbase.watcher")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    stopping = False

    def handle_stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    logger.info("Watcher de desconexiones iniciando…")
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        logger.info("Advisory lock adquirido; esta instancia es la activa")
        next_retention = time.monotonic() + 60
        try:
            while not stopping:
                try:
                    with SessionLocal() as db:
                        setting = settings_service.get_settings(db)
                        alert_service.check_disconnected_devices(db, setting)
                        db.commit()
                except Exception:
                    logger.exception("Error en el ciclo de desconexiones")

                if time.monotonic() >= next_retention:
                    try:
                        with SessionLocal() as db:
                            result = run_retention(db)
                        logger.info("Retención: %s", result.summary())
                    except Exception:
                        logger.exception("Error en el ciclo de retención")
                    next_retention = time.monotonic() + max(
                        3600, settings.retention_check_seconds
                    )

                deadline = time.monotonic() + max(1, settings.disconnect_check_seconds)
                while not stopping and time.monotonic() < deadline:
                    time.sleep(min(0.5, deadline - time.monotonic()))
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}
            )
    logger.info("Watcher detenido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
