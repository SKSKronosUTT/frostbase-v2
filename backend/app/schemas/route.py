from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DeliveryPointIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    order_index: int | None = None


class DeliveryPointOut(BaseModel):
    id: int
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    order_index: int


class RouteCreate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["activa", "inactiva"] = "activa"
    points: list[DeliveryPointIn] = Field(min_length=2, max_length=50)

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[DeliveryPointIn]) -> list[DeliveryPointIn]:
        coordinates = {(p.latitude, p.longitude) for p in points}
        if len(coordinates) < 2:
            raise ValueError("La ruta necesita al menos dos coordenadas distintas")
        return points


class RouteUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["activa", "inactiva"] | None = None
    points: list[DeliveryPointIn] = Field(min_length=2, max_length=50)

    @field_validator("points")
    @classmethod
    def validate_points(cls, points: list[DeliveryPointIn]) -> list[DeliveryPointIn]:
        coordinates = {(p.latitude, p.longitude) for p in points}
        if len(coordinates) < 2:
            raise ValueError("La ruta necesita al menos dos coordenadas distintas")
        return points


class RouteBrief(BaseModel):
    id: int
    name: str
    status: str


class AssignedTruckOut(BaseModel):
    id: int
    plate: str
    brand: str
    model: str


class AssignedDriverOut(BaseModel):
    id: int
    full_name: str


WEEKDAY_LABELS = (
    "domingo",
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
)


def _validate_weekdays(weekdays: list[int]) -> list[int]:
    if len(set(weekdays)) != len(weekdays):
        raise ValueError("los días de entrega no pueden repetirse")
    for weekday in weekdays:
        if not 0 <= weekday <= 6:
            raise ValueError(f"día inválido: {weekday} (0=domingo … 6=sábado)")
    return sorted(weekdays)


class RouteDriverIn(BaseModel):
    """Asignación de conductor y calendario semanal de la ruta (G4).

    ``driver_id = null`` quita al conductor y su calendario.
    """

    driver_id: int | None = None
    weekdays: list[int] = Field(default_factory=list, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def _valid_weekdays(cls, weekdays: list[int]) -> list[int]:
        return _validate_weekdays(weekdays)


class RouteOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    geometry: list | None = None
    points: list[DeliveryPointOut]
    truck: AssignedTruckOut | None = None
    assigned_driver: AssignedDriverOut | None = None
    delivery_days: list[int] = []
    created_at: datetime
    updated_at: datetime
    warning: str | None = None
    geometry_status: str = "ready"


class RouteBriefWithGeometry(RouteBrief):
    geometry: list | None = None


class AssignTruckIn(BaseModel):
    truck_id: int
