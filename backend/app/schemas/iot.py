from datetime import datetime, timedelta

from pydantic import BaseModel, Field, field_validator

from app.schemas.alert import AlertOut
from app.utils.time import ensure_utc, utcnow

TIMESTAMP_PAST_DAYS = 7
TIMESTAMP_FUTURE_MINUTES = 5


class ReadingIngest(BaseModel):
    device_id: str = Field(min_length=3, max_length=100)
    temperature: float = Field(ge=-80, le=80)
    humidity: float = Field(ge=0, le=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timestamp: datetime | None = None

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = ensure_utc(value)
        if normalized is None:
            return None
        now = utcnow()
        if normalized > now + timedelta(minutes=TIMESTAMP_FUTURE_MINUTES):
            raise ValueError(
                f"timestamp no puede estar más de {TIMESTAMP_FUTURE_MINUTES} "
                "minutos en el futuro"
            )
        if normalized < now - timedelta(days=TIMESTAMP_PAST_DAYS):
            raise ValueError(
                f"timestamp no puede ser anterior a {TIMESTAMP_PAST_DAYS} días"
            )
        return normalized


class IoTReadingResponse(BaseModel):
    success: bool
    message: str
    truck_id: int | None = None
    alerts: list[AlertOut] = []
    duplicate: bool = False
    reading_id: int | None = None


class DoorEventIngest(BaseModel):
    """Evento del Reed Switch: se envía solo cuando la puerta cambia."""

    device_id: str = Field(min_length=3, max_length=100)
    is_open: bool
    timestamp: datetime | None = None

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = ensure_utc(value)
        if normalized is None:
            return None
        now = utcnow()
        if normalized > now + timedelta(minutes=TIMESTAMP_FUTURE_MINUTES):
            raise ValueError(
                f"timestamp no puede estar más de {TIMESTAMP_FUTURE_MINUTES} "
                "minutos en el futuro"
            )
        if normalized < now - timedelta(days=TIMESTAMP_PAST_DAYS):
            raise ValueError(
                f"timestamp no puede ser anterior a {TIMESTAMP_PAST_DAYS} días"
            )
        return normalized


class DoorEventResponse(BaseModel):
    success: bool
    message: str
    truck_id: int | None = None
    door_open: bool
    duplicate: bool = False
    event_id: int | None = None


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
