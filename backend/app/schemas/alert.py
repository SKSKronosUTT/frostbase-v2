from datetime import datetime

from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    truck_id: int | None = None
    truck_plate: str | None = None
    device_id: int | None = None
    device_identifier: str | None = None
    alert_type: str
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    message: str | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    status: str
