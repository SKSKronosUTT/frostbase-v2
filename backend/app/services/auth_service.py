import logging
import secrets
import threading
import time
from collections import deque

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.admin import Admin
from app.repositories import admin as admin_repo
from app.utils.time import utcnow

logger = logging.getLogger("frostbase.auth")

# Hash de referencia para que un usuario inexistente cueste lo mismo que uno
# existente con contraseña incorrecta (evita un oráculo de tiempo).
_DUMMY_HASH = hash_password(secrets.token_urlsafe(24))

_FAILURE_WINDOW_SECONDS = 15 * 60
_FAILURE_THRESHOLD = 5
_LOCK_STEPS_SECONDS = (60, 300, 900)
_failure_lock = threading.Lock()
_failures: dict[str, deque[float]] = {}
_locked_until: dict[str, float] = {}


class AuthenticationError(Exception):
    pass


class PasswordPolicyError(Exception):
    pass


def _normalize_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def is_login_locked(identifier: str) -> int:
    """Devuelve los segundos restantes de bloqueo, o 0 si no está bloqueado."""
    key = _normalize_identifier(identifier)
    with _failure_lock:
        until = _locked_until.get(key)
        if until is None:
            return 0
        remaining = int(until - time.monotonic())
        if remaining <= 0:
            _locked_until.pop(key, None)
            return 0
        return remaining


def register_failed_login(identifier: str) -> None:
    """Aplica un bloqueo progresivo por identificador (memoria del proceso).

    El límite distribuido de T2.1 (Redis) sigue siendo la primera barrera; este
    contador añade una espera creciente tras varios fallos.
    """
    key = _normalize_identifier(identifier)
    now = time.monotonic()
    with _failure_lock:
        events = _failures.setdefault(key, deque())
        cutoff = now - _FAILURE_WINDOW_SECONDS
        while events and events[0] <= cutoff:
            events.popleft()
        events.append(now)
        if len(events) >= _FAILURE_THRESHOLD:
            step = min(len(events) // _FAILURE_THRESHOLD, len(_LOCK_STEPS_SECONDS)) - 1
            _locked_until[key] = now + _LOCK_STEPS_SECONDS[step]


def clear_login_failures(identifier: str) -> None:
    key = _normalize_identifier(identifier)
    with _failure_lock:
        _failures.pop(key, None)
        _locked_until.pop(key, None)


def reset_login_throttle() -> None:
    """Limpia el estado de bloqueo (tests y mantenimiento)."""
    with _failure_lock:
        _failures.clear()
        _locked_until.clear()


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


def authenticate(
    db: Session, identifier: str, password: str, client_ip: str | None = None
) -> Admin:
    admin = admin_repo.get_by_identifier(db, identifier)
    # Siempre se ejecuta una verificación: con el hash real si el usuario existe
    # y con el hash dummy si no, para que la latencia no revele su existencia.
    password_hash = admin.password_hash if admin is not None else _DUMMY_HASH
    is_valid = verify_password(password, password_hash)
    if admin is None or not is_valid:
        logger.warning(
            "login_failed identifier=%s ip=%s result=denied",
            _normalize_identifier(identifier),
            client_ip or "unknown",
        )
        raise AuthenticationError("Usuario o contraseña incorrectos")
    admin.last_login = utcnow()
    db.add(admin)
    db.flush()
    logger.info(
        "login_ok identifier=%s ip=%s result=allowed",
        admin.username,
        client_ip or "unknown",
    )
    return admin


def change_password(
    db: Session, admin: Admin, current_password: str, new_password: str
) -> Admin:
    if not verify_password(current_password, admin.password_hash):
        raise AuthenticationError("La contraseña actual no es correcta")
    if new_password.lower() == current_password.lower():
        raise PasswordPolicyError("La nueva contraseña debe ser distinta de la actual")
    if admin.username.lower() in new_password.lower():
        raise PasswordPolicyError(
            "La nueva contraseña no puede contener el nombre de usuario"
        )

    admin.password_hash = hash_password(new_password)
    admin.must_change_password = False
    admin.token_version += 1
    db.add(admin)
    db.flush()
    logger.info("Contraseña actualizada para el administrador %s", admin.username)
    return admin


def get_admin(db: Session, admin_id: int) -> Admin | None:
    return admin_repo.get_by_id(db, admin_id)


def update_theme(db: Session, admin: Admin, theme: str) -> Admin:
    admin.theme = theme
    db.add(admin)
    db.flush()
    return admin
