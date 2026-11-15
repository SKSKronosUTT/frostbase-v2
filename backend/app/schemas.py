from datetime import date as date_type
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LoginIn(APIModel):
    email: str
    password: str


class StoreLocationIn(APIModel):
    address: str
    latitude: float
    longitude: float


class StoreIn(APIModel):
    name: str
    phone: str | None = None
    location: StoreLocationIn
    active: bool = True


class TruckIn(APIModel):
    brand: str
    model: str
    license_plate: str
    id_state_truck: str = "AV"


class UserIn(APIModel):
    first_name: str
    last_name: str
    middle_name: str | None = None
    email: str
    phone: str | None = None
    birth_date: date_type | None = None
    password: str
    is_admin: bool = False
    id_truck_default: str | None = None


class UserUpdate(APIModel):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    email: str | None = None
    phone: str | None = None
    birth_date: date_type | None = None
    password: str | None = None
    is_admin: bool | None = None
    id_truck_default: str | None = None
    active: bool | None = None


class OrderIn(APIModel):
    date: datetime | None = None
    id_store: str
    id_created_by_user: str | None = None


class OrderUpdate(APIModel):
    date: datetime | None = None
    delivered: datetime | None = None
    id_store: str | None = None
    id_created_by_user: str | None = None
    id_state_order: str | None = None


class RouteStoreIn(APIModel):
    store_id: str
    sequence: int


class RouteIn(APIModel):
    name: str
    deliver_days: list[int] = Field(default_factory=list)
    id_assigned_user: str | None = None
    stores: list[RouteStoreIn] = Field(default_factory=list)
    active: bool = True


class ReadingIn(APIModel):
    date: datetime | None = None
    door_state: bool = False
    temp: float
    humidity: int
    latitude: float
    longitude: float
    truck_id: str | None = None


class AlertIn(APIModel):
    date: datetime | None = None
    state: bool = True
    alert_type: str
    reading: str | None = None


class AlertUpdate(APIModel):
    date: datetime | None = None
    state: bool | None = None
    alert_type: str | None = None
    reading: str | None = None


class ParameterIn(APIModel):
    max_temperature: float
    min_temperature: float
    max_humidity: int
    min_humidity: int


class TripStartIn(APIModel):
    truck_id: str
    driver_id: str
    route_id: str
    start_date: datetime | None = None


class SimulateIn(APIModel):
    date: date_type | None = None


class TripCreateIn(APIModel):
    start_time: datetime
    end_time: datetime | None = None
    id_truck: str
    id_driver: str
    id_route: str
    id_state: str = "IP"
