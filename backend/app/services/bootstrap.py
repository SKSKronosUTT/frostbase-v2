import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import Base, engine
from app.services import auth_service, settings_service

logger = logging.getLogger("frostbase.bootstrap")


def ensure_schema() -> None:
    if settings.auto_create_tables:
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)


def bootstrap_database(db: Session) -> None:
    settings_service.get_settings(db)
    auth_service.ensure_initial_admin(db)
    logger.info("Base de datos inicializada correctamente")
