from datetime import datetime

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    truck_id: int | None = None


class DeviceUpdate(BaseModel):
    truck_id: int | None = None


class DeviceOut(BaseModel):
    id: int
    device_id: str
    truck_id: int | None = None
    truck_plate: str | None = None
    is_online: bool = False
    last_seen: datetime | None = None
    created_at: datetime


class DeviceCreatedOut(DeviceOut):
    device_key: str
