from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.alert import AlertOut
from app.schemas.route import RouteBriefWithGeometry


class ReadingIngest(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    temperature: float = Field(ge=-80, le=80)
    humidity: float = Field(ge=0, le=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timestamp: datetime | None = None


class IoTReadingResponse(BaseModel):
    success: bool
    message: str
    truck_id: int | None = None
    alerts: list[AlertOut] = []


class IoTRouteConfig(BaseModel):
    name: str
    geometry: list | None = None


class IoTConfigResponse(BaseModel):
    device_id: str
    truck_id: int | None = None
    truck_plate: str | None = None
    route: IoTRouteConfig | None = None
    temperature_min: float
    temperature_max: float
    humidity_min: float
    humidity_max: float
