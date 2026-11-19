"""Aplica las migraciones de Alembic con un advisory lock de PostgreSQL.

El lock evita carreras cuando varias réplicas del servicio arrancan a la vez.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine

LOCK_KEY = 7712026
BACKEND_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            command.upgrade(config, "head")
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}
            )


if __name__ == "__main__":
    main()
