import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.services import alert_service, settings_service
from app.services.bootstrap import bootstrap_database, ensure_schema

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("frostbase")


async def _disconnect_watcher() -> None:
    while True:
        try:
            await asyncio.sleep(settings.disconnect_check_seconds)
            with SessionLocal() as db:
                setting = settings_service.get_settings(db)
                alert_service.check_disconnected_devices(db, setting)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error al revisar dispositivos desconectados")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_schema()
    with SessionLocal() as db:
        bootstrap_database(db)
    if settings.is_production and settings.secret_key.startswith("dev-only"):
        logger.error("SECRET_KEY insegura en producción. Configure una clave real.")
    task = asyncio.create_task(_disconnect_watcher())
    logger.info("FrostBase iniciado en entorno '%s'", settings.environment)
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Sistema"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.project_name}


frontend_path = settings.frontend_path
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    logger.warning("No se encontró el directorio frontend en %s", frontend_path)
