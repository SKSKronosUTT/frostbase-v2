from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    middle_name: str | None = None
    email: str
    phone: str
    must_change_password: bool = False
    created_at: datetime
    last_login: datetime | None = None


class DriverTruckBrief(BaseModel):
    id: int
    plate: str


class DriverMeOut(DriverOut):
    truck: DriverTruckBrief | None = None
