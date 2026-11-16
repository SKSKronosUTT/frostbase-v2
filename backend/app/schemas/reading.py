from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    truck_id: int | None = None
    temperature: float
    humidity: float
    latitude: float | None = None
    longitude: float | None = None
    received_at: datetime
    reading_timestamp: datetime
