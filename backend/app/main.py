import asyncio
import contextlib
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.http import close_http_client
from app.core.logging import request_id_ctx, setup_logging
from app.services import alert_service, settings_service
from app.services.bootstrap import bootstrap_database, ensure_schema

setup_logging(settings.log_level)
logger = logging.getLogger("frostbase")

CSP_REPORT_ONLY = (
    "default-src 'self'; "
    "img-src 'self' data: https://*.tile.openstreetmap.org; "
    "style-src 'self'; "
    "script-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'"
)


@lru_cache
def _alembic_head() -> str | None:
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


async def _disconnect_watcher() -> None:
    while True:
        try:
            await asyncio.sleep(settings.disconnect_check_seconds)
            with SessionLocal() as db:
                setting = settings_service.get_settings(db)
                alert_service.check_disconnected_devices(db, setting)
                db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error al revisar dispositivos desconectados")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Configuración efectiva: environment=%s cors=%s cookie_secure=%s "
        "auto_create_tables=%s rate_limit_backend=%s allowed_hosts=%s",
        settings.environment,
        ",".join(settings.cors_origin_list) or "(sin orígenes)",
        settings.cookie_secure,
        settings.auto_create_tables,
        settings.rate_limit_backend,
        ",".join(settings.allowed_host_list),
    )
    ensure_schema()
    with SessionLocal() as db:
        bootstrap_database(db)
    task = (
        asyncio.create_task(_disconnect_watcher())
        if settings.enable_inprocess_watcher
        else None
    )
    logger.info("FrostBase iniciado en entorno '%s'", settings.environment)
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await close_http_client()
        logger.info("FrostBase detenido")


app = FastAPI(
    title="FrostBase API",
    description=(
        "API de monitoreo de camiones refrigerados. Incluye autenticación "
        "administrativa con JWT y una API independiente para dispositivos ESP32-S3."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    method = request.method
    path = request.url.path

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "request_failed",
            extra={
                "method": method,
                "path": path,
                "duration_ms": round(duration_ms, 1),
            },
        )
        request_id_ctx.reset(token)
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = (
        "geolocation=(self), camera=(), microphone=()"
    )
    response.headers["Content-Security-Policy-Report-Only"] = CSP_REPORT_ONLY
    logger.info(
        "request_completed",
        extra={
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 1),
        },
    )
    request_id_ctx.reset(token)
    return response


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        path = request.url.path
        api_prefix = settings.api_v1_prefix
        is_exempt = (
            not path.startswith(api_prefix)
            or path.startswith(f"{api_prefix}/iot/")
            or path == f"{api_prefix}/auth/login"
        )
        if not is_exempt:
            has_session_cookie = bool(request.cookies.get(settings.cookie_name))
            uses_bearer = request.headers.get("Authorization", "").lower().startswith(
                "bearer "
            )
            if has_session_cookie and not uses_bearer:
                cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
                header_token = request.headers.get("X-CSRF-Token", "")
                if (
                    not cookie_token
                    or not header_token
                    or not hmac.compare_digest(cookie_token, header_token)
                ):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "CSRF token inválido o ausente"},
                    )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.project_name}


@app.get("/health/live", tags=["Sistema"])
def live() -> dict[str, str]:
    return {"status": "ok", "service": settings.project_name}


@app.get("/health/ready", tags=["Sistema"])
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de datos no disponible",
        ) from exc

    head = _alembic_head()
    if head is not None and version != head:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Esquema desactualizado: {version} != {head}",
        )
    return {
        "status": "ready",
        "service": settings.project_name,
        "schema": version or "",
    }


frontend_path = settings.frontend_path
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning("No se encontró el directorio frontend en %s", frontend_path)
