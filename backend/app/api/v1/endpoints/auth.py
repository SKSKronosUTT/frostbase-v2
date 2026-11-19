from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.security import create_access_token
from app.models.admin import Admin
from app.schemas.auth import (
    AdminOut,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    ThemeUpdate,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


def _set_session_cookie(response: Response, admin: Admin) -> None:
    token = create_access_token(str(admin.id), token_version=admin.token_version)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> LoginResponse:
    try:
        admin = auth_service.authenticate(db, payload.identifier, payload.password)
    except auth_service.AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    _set_session_cookie(response, admin)
    return LoginResponse(admin=AdminOut.model_validate(admin))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")


@router.get("/me", response_model=AdminOut)
def me(admin: CurrentAdmin) -> AdminOut:
    return AdminOut.model_validate(admin)


@router.put("/preferences", response_model=AdminOut)
def update_preferences(
    payload: ThemeUpdate, admin: CurrentAdmin, db: DbSession
) -> AdminOut:
    updated = auth_service.update_theme(db, admin, payload.theme)
    return AdminOut.model_validate(updated)


@router.post("/change-password", response_model=AdminOut)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    admin: CurrentAdmin,
    db: DbSession,
) -> AdminOut:
    try:
        updated = auth_service.change_password(
            db, admin, payload.current_password, payload.new_password
        )
    except auth_service.AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except auth_service.PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    # La versión del token cambió: se reemite la cookie de esta sesión.
    _set_session_cookie(response, updated)
    return AdminOut.model_validate(updated)
