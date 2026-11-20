from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.device import DeviceOut
from app.schemas.reading import ReadingOut
from app.schemas.route import RouteBrief, RouteOut

TruckStatus = Literal["en_ruta", "disponible", "mantenimiento"]


class TruckCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1950, le=2100)
    plate: str = Field(min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    status: TruckStatus = "disponible"
    route_id: int | None = None
    device_id: int | None = None

    def normalized_plate(self) -> str:
        return self.plate.strip().upper()


class TruckUpdate(BaseModel):
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    year: int | None = Field(default=None, ge=1950, le=2100)
    plate: str | None = Field(default=None, min_length=2, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    status: TruckStatus | None = None
    route_id: int | None = None
    device_id: int | None = None


class TruckOut(BaseModel):
    id: int
    brand: str
    model: str
    year: int
    plate: str
    description: str | None = None
    status: str
    route: RouteBrief | None = None
    device: DeviceOut | None = None
    current_reading: ReadingOut | None = None
    active_alerts: int = 0
    created_at: datetime


class TruckDetailOut(TruckOut):
    route: RouteOut | None = None  # type: ignore[assignment]
    temperature_min: float | None = None
    temperature_max: float | None = None
    humidity_min: float | None = None
    humidity_max: float | None = None
