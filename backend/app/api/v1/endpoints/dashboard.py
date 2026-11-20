from fastapi import APIRouter

from app.api.deps import CurrentAdmin, DbSession
from app.schemas.dashboard import DashboardAlert, DashboardSummary, DashboardTruck, WeatherOut
from app.services import dashboard_service, weather_service

router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"], dependencies=[],
)


@router.get("/summary", response_model=DashboardSummary)
def summary(db: DbSession, _: CurrentAdmin) -> DashboardSummary:
    return dashboard_service.get_summary(db)


@router.get("/trucks", response_model=list[DashboardTruck])
def trucks(db: DbSession, _: CurrentAdmin) -> list[DashboardTruck]:
    return dashboard_service.get_trucks(db)


@router.get("/alerts", response_model=list[DashboardAlert])
def alerts(db: DbSession, _: CurrentAdmin) -> list[DashboardAlert]:
    return dashboard_service.get_alerts(db)


@router.get("/weather", response_model=WeatherOut)
async def weather(db: DbSession, _: CurrentAdmin) -> WeatherOut:
    return await weather_service.get_weather(db)
