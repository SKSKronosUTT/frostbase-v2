from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.admin import Admin
from app.repositories import admin as admin_repo
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


def get_current_admin(request: Request, db: DbSession) -> Admin:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if payload is None or payload.get("type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        admin_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        admin_id = -1
    admin = admin_repo.get_by_id(db, admin_id)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin


CurrentAdmin = Annotated[Admin, Depends(get_current_admin)]


def authenticate_device_or_401(
    db: Session, *, device_id: str, device_key: str | None
):
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
