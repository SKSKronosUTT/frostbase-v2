from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.driver import Driver


def get_by_email(db: Session, email: str) -> Driver | None:
    return db.scalar(
        select(Driver).where(func.lower(Driver.email) == email.strip().lower())
    )


def get_by_id(db: Session, driver_id: int) -> Driver | None:
    return db.get(Driver, driver_id)
