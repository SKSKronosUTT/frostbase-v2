from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.admin import Admin
from app.models.driver import Driver
from app.repositories import admin as admin_repo
from app.repositories import driver as driver_repo
from app.services import device_service

DbSession = Annotated[Session, Depends(get_db)]


def _token_from_request(request: Request) -> str | None:
    token = request.cookies.get(settings.cookie_name)
    if token:
        return token
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _decode(token: str) -> dict:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def _subject_id(payload: dict) -> int:
    try:
        return int(payload.get("sub", ""))
    except (TypeError, ValueError):
        return -1


def get_current_admin(request: Request, db: DbSession) -> Admin:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode(token)
    if payload.get("type") == "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso solo para administradores",
        )
    admin = admin_repo.get_by_id(db, _subject_id(payload))
    if admin is None or payload.get("tv") != admin.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.admin_id = admin.id
    return admin


def get_current_driver(request: Request, db: DbSession) -> Driver:
    """Sesión del conductor: el ID siempre viene del token, nunca del cliente."""
    token = _token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode(token)
    if payload.get("type") == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso solo para conductores",
        )
    driver = driver_repo.get_by_id(db, _subject_id(payload))
    if (
        driver is None
        or not driver.is_active
        or payload.get("tv") != driver.token_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.driver_id = driver.id
    return driver


def get_current_principal(request: Request, db: DbSession) -> Admin | Driver:
    """Sesión válida de cualquier rol (login compartido, G2).

    Usada por ``/auth/refresh`` y ``/auth/change-password``; los endpoints con
    rol específico usan ``CurrentAdmin`` / ``CurrentDriver``.
    """
    token = _token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode(token)
    token_type = payload.get("type")
    account_id = _subject_id(payload)

    if token_type == "admin":
        admin = admin_repo.get_by_id(db, account_id)
        if admin is None or payload.get("tv") != admin.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida o expirada",
                headers={"WWW-Authenticate": "Bearer"},
            )
        request.state.admin_id = admin.id
        return admin

    if token_type == "driver":
        driver = driver_repo.get_by_id(db, account_id)
        if (
            driver is None
            or not driver.is_active
            or payload.get("tv") != driver.token_version
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida o expirada",
                headers={"WWW-Authenticate": "Bearer"},
            )
        request.state.driver_id = driver.id
        return driver

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]
CurrentDriver = Annotated[Driver, Depends(get_current_driver)]
CurrentPrincipal = Annotated[Admin | Driver, Depends(get_current_principal)]


def authenticate_device_or_401(db: Session, *, device_id: str, device_key: str | None):
    if not device_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el encabezado X-Device-Key",
        )
    device = device_service.authenticate_device(db, device_id, device_key)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dispositivo o clave inválidos",
        )
    return device


def get_device_headers(
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
    x_device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> tuple[str | None, str | None]:
    return x_device_id, x_device_key
