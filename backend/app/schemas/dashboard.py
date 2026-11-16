from datetime import datetime

from pydantic import BaseModel

from app.schemas.route import RouteBriefWithGeometry


class DashboardSummary(BaseModel):
    total_trucks: int
    active_trucks: int
    avg_temperature: float | None = None
    effectiveness: float | None = None
    readings_24h: int
    active_alerts: int
    trucks_by_status: dict[str, int]
    last_update: datetime | None = None
    generated_at: datetime


class DashboardTruck(BaseModel):
    id: int
    plate: str
    brand: str
    model: str
    status: str
    temperature: float | None = None
    humidity: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    last_update: datetime | None = None
    device_online: bool = False
    reading_status: str = "sin_lectura"
    route: RouteBriefWithGeometry | None = None
    active_alerts: int = 0


class DashboardAlert(BaseModel):
    id: int
    truck_id: int | None = None
    truck_plate: str | None = None
    device_identifier: str | None = None
    alert_type: str
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    message: str | None = None
    started_at: datetime


class WeatherOut(BaseModel):
    available: bool
    city: str
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    condition: str | None = None
    icon: str | None = None
    updated_at: datetime | None = None
    stale: bool = False
    error: str | None = None
