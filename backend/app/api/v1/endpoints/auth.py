import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import CurrentAdmin, CurrentPrincipal, DbSession
from app.core.config import settings
from app.core.ratelimit import RateLimit, client_ip
from app.core.security import create_access_token
from app.models.admin import Admin
from app.models.driver import Driver
from app.schemas.auth import (
    AdminOut,
    DriverOut,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    SessionResponse,
    ThemeUpdate,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Autenticación"])

_login_ip_limiter = RateLimit(
    "login:ip", limit=settings.login_ip_rate_limit, window_seconds=60
)
_login_identifier_limiter = RateLimit(
    "login:identifier", limit=settings.login_identifier_rate_limit, window_seconds=900
)


def _principal_role(principal: Admin | Driver) -> str:
    return "admin" if isinstance(principal, Admin) else "driver"


def _set_session_cookie(response: Response, principal: Admin | Driver) -> None:
    role = _principal_role(principal)
    token = create_access_token(
        str(principal.id),
        token_version=principal.token_version,
        token_type=role,  # type: ignore[arg-type]
    )
    max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=secrets.token_urlsafe(32),
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=max_age,
        path="/",
    )


def _session_response(principal: Admin | Driver) -> SessionResponse:
    if isinstance(principal, Admin):
        return SessionResponse(role="admin", admin=AdminOut.model_validate(principal))
    return SessionResponse(role="driver", driver=DriverOut.model_validate(principal))


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: DbSession
) -> LoginResponse:
    identifier = payload.identifier.strip().lower()
    locked_for = auth_service.is_login_locked(identifier)
    if locked_for:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Inténtalo de nuevo más tarde.",
            headers={"Retry-After": str(locked_for)},
        )

    _login_ip_limiter.check(request, response)
    _login_identifier_limiter.check(request, response, extra=identifier)

    try:
        principal = auth_service.authenticate_principal(
            db, payload.identifier, payload.password, client_ip=client_ip(request)
        )
    except auth_service.AuthenticationError as exc:
        auth_service.register_failed_login(identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    auth_service.clear_login_failures(identifier)
    _set_session_cookie(response, principal)

    if isinstance(principal, Admin):
        return LoginResponse(role="admin", admin=AdminOut.model_validate(principal))
    return LoginResponse(role="driver", driver=DriverOut.model_validate(principal))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


@router.post("/refresh", response_model=SessionResponse)
def refresh(response: Response, principal: CurrentPrincipal) -> SessionResponse:
    _set_session_cookie(response, principal)
    return _session_response(principal)


@router.get("/me", response_model=AdminOut)
def me(admin: CurrentAdmin) -> AdminOut:
    return AdminOut.model_validate(admin)


@router.get("/session", response_model=SessionResponse)
def session(principal: CurrentPrincipal) -> SessionResponse:
    """Rol de la sesión actual (login compartido admin/conductor)."""
    return _session_response(principal)


@router.put("/preferences", response_model=AdminOut)
def update_preferences(
    payload: ThemeUpdate, admin: CurrentAdmin, db: DbSession
) -> AdminOut:
    updated = auth_service.update_theme(db, admin, payload.theme)
    return AdminOut.model_validate(updated)


@router.post("/change-password", response_model=SessionResponse)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    principal: CurrentPrincipal,
    db: DbSession,
) -> SessionResponse:
    try:
        if isinstance(principal, Admin):
            updated: Admin | Driver = auth_service.change_password(
                db, principal, payload.current_password, payload.new_password
            )
        else:
            updated = auth_service.change_driver_password(
                db, principal, payload.current_password, payload.new_password
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
    return _session_response(updated)
