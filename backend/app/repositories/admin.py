from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.admin import Admin


def get_by_identifier(db: Session, identifier: str) -> Admin | None:
    normalized = identifier.strip().lower()
    return db.scalar(
        select(Admin).where(
            or_(Admin.username == normalized, Admin.email == normalized)
        )
    )


def get_by_id(db: Session, admin_id: int) -> Admin | None:
    return db.get(Admin, admin_id)


def create(db: Session, *, username: str, email: str, password_hash: str) -> Admin:
    admin = Admin(
        username=username.strip().lower(),
        email=email.strip().lower(),
        password_hash=password_hash,
    )
    db.add(admin)
    db.flush()
    return admin


def count(db: Session) -> int:
    return db.scalar(select(func.count(Admin.id))) or 0
