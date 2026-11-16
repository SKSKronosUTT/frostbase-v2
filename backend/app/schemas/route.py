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


class RouteOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    geometry: list | None = None
    points: list[DeliveryPointOut]
    truck: AssignedTruckOut | None = None
    created_at: datetime
    updated_at: datetime
    warning: str | None = None


class RouteBriefWithGeometry(RouteBrief):
    geometry: list | None = None


class AssignTruckIn(BaseModel):
    truck_id: int
