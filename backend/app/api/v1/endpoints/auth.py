from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentAdmin, DbSession
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import AdminOut, LoginRequest, LoginResponse, ThemeUpdate
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> LoginResponse:
    try:
        admin = auth_service.authenticate(db, payload.identifier, payload.password)
    except auth_service.AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    token = create_access_token(str(admin.id))
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
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
