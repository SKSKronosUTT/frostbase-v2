from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    alerts,
    auth,
    dashboard,
    devices,
    driver,
    drivers,
    iot,
    readings,
    routes,
    settings,
    trucks,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(trucks.router)
api_router.include_router(devices.router)
api_router.include_router(routes.router)
api_router.include_router(readings.router)
api_router.include_router(alerts.router)
api_router.include_router(settings.router)
api_router.include_router(iot.router)
api_router.include_router(driver.router)
api_router.include_router(drivers.router)
api_router.include_router(ai.router)
