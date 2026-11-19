import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.admin import Admin
from app.repositories import admin as admin_repo
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.auth")


class AuthenticationError(Exception):
    pass


class PasswordPolicyError(Exception):
    pass


def ensure_initial_admin(db: Session) -> Admin | None:
    if admin_repo.count(db):
        return None
    admin = admin_repo.create(
        db,
        username=settings.admin_username,
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
    )
    logger.info("Administrador inicial creado: %s", admin.username)
    return admin


def authenticate(db: Session, identifier: str, password: str) -> Admin:
    admin = admin_repo.get_by_identifier(db, identifier)
    if admin is None or not verify_password(password, admin.password_hash):
        raise AuthenticationError("Usuario o contraseña incorrectos")
    admin.last_login = utcnow()
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def change_password(
    db: Session, admin: Admin, current_password: str, new_password: str
) -> Admin:
    if not verify_password(current_password, admin.password_hash):
        raise AuthenticationError("La contraseña actual no es correcta")
    if new_password.lower() == current_password.lower():
        raise PasswordPolicyError(
            "La nueva contraseña debe ser distinta de la actual"
        )
    if admin.username.lower() in new_password.lower():
        raise PasswordPolicyError(
            "La nueva contraseña no puede contener el nombre de usuario"
        )

    admin.password_hash = hash_password(new_password)
    admin.must_change_password = False
    admin.token_version += 1
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Contraseña actualizada para el administrador %s", admin.username)
    return admin


def get_admin(db: Session, admin_id: int) -> Admin | None:
    return admin_repo.get_by_id(db, admin_id)


def update_theme(db: Session, admin: Admin, theme: str) -> Admin:
    admin.theme = theme
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
