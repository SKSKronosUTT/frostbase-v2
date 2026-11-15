from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, FRONTEND_DIR
from .db import init_db
from .deps import current_admin, current_user
from .routers import (
    alerts,
    auth,
    dashboard,
    orders,
    parameters,
    readings,
    routes,
    simulator,
    stores,
    trips,
    trucks,
    users,
)
from .services.seed import seed_if_enabled


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_enabled()
    yield


app = FastAPI(
    title="Frostbase API",
    description="API de flota, pedidos y monitoreo de cadena de frío para Frostbase.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")

for router in (
    users.router,
    trucks.router,
    stores.router,
    orders.router,
    routes.router,
    trips.router,
    readings.router,
    alerts.router,
    parameters.router,
    dashboard.router,
):
    app.include_router(router, prefix="/api", dependencies=[Depends(current_user)])

app.include_router(simulator.router, prefix="/api", dependencies=[Depends(current_admin)])


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok", "service": "frostbase"}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
