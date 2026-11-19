import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine
from app.services import auth_service, settings_service

logger = logging.getLogger("frostbase.bootstrap")

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def ensure_schema() -> None:
    """Crea el esquema solo en desarrollo/tests y deja Alembic en ``head``.

    En producción ``AUTO_CREATE_TABLES`` debe ser ``false`` y el esquema lo
    gobierna exclusivamente ``scripts/migrate.py`` (Alembic).
    """
    if not settings.auto_create_tables:
        return

    import app.models  # noqa: F401

    logger.warning(
        "AUTO_CREATE_TABLES activo: creando tablas con SQLAlchemy. "
        "Uso permitido solo en desarrollo/tests."
    )
    Base.metadata.create_all(bind=engine)
    command.stamp(_alembic_config(), "head")


def bootstrap_database(db: Session) -> None:
    settings_service.get_settings(db)
    auth_service.ensure_initial_admin(db)
    logger.info("Base de datos inicializada correctamente")
