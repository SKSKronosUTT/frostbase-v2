from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # G8 (RNF2): el portal puede mantener cientos de peticiones en vuelo
    # (999 usuarios × polling 5 s). Un pool de 10+20 por worker agotaba y
    # las peticiones morían con TimeoutError tras 30 s de cola.
    pool_size=40,
    max_overflow=10,
    pool_timeout=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Una transacción por petición; commit al salir sin excepción."""
    with SessionLocal() as db:
        with db.begin():
            yield db
