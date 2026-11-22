"""Schemas del portal del conductor (G5): solo lectura."""

from datetime import datetime

from pydantic import BaseModel


class DriverContainerOut(BaseModel):
    """Estado del contenedor con umbrales efectivos y última lectura."""

    temperature: float | None = None
    humidity: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    received_at: datetime | None = None
    status: str = "no_data"
    temperature_min: float | None = None
    temperature_max: float | None = None
    humidity_min: float | None = None
    humidity_max: float | None = None
    door_open: bool | None = None
    door_event_at: datetime | None = None


class DriverTruckCard(BaseModel):
    id: int
    plate: str
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    status: str | None = None


class DriverRouteCard(BaseModel):
    id: int
    name: str
    status: str
    delivery_days: list[int] = []
    points_count: int = 0


class DriverRouteDetail(BaseModel):
    id: int
    name: str
    status: str
    description: str | None = None
    delivery_days: list[int] = []
    geometry: list | None = None
    points: list[dict] = []


class DriverDashboardOut(BaseModel):
    driver: dict
    truck: DriverTruckCard | None = None
    today_route: DriverRouteCard | None = None
    routes: list[DriverRouteCard] = []
    container: DriverContainerOut | None = None
    active_alerts: int = 0


class DriverAlertOut(BaseModel):
    id: int
    alert_type: str
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    message: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    status: str
    acknowledged_at: datetime | None = None


class DriverReadingOut(BaseModel):
    temperature: float
    humidity: float
    latitude: float | None = None
    longitude: float | None = None
    received_at: datetime
    reading_timestamp: datetime
