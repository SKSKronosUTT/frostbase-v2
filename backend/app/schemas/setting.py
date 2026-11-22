from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SettingsOut(BaseModel):
    temperature_ideal: float
    temperature_tolerance: float
    humidity_ideal: float
    humidity_tolerance: float
    temperature_min: float
    temperature_max: float
    humidity_min: float
    humidity_max: float
    offline_timeout_seconds: int
    door_open_grace_seconds: int
    weather_city: str
    weather_latitude: float
    weather_longitude: float
    updated_at: datetime


class SettingsUpdate(BaseModel):
    temperature_ideal: float = Field(ge=-50, le=30)
    temperature_tolerance: float = Field(gt=0, le=30)
    humidity_ideal: float = Field(ge=0, le=100)
    humidity_tolerance: float = Field(gt=0, le=50)
    offline_timeout_seconds: int = Field(ge=10, le=86400)
    door_open_grace_seconds: int | None = Field(default=None, ge=5, le=600)
    weather_city: str = Field(min_length=1, max_length=120)
    weather_latitude: float = Field(ge=-90, le=90)
    weather_longitude: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SettingsUpdate":
        if self.temperature_ideal - self.temperature_tolerance < -80:
            raise ValueError(
                "El límite mínimo de temperatura no puede ser menor a -80 °C"
            )
        if self.temperature_ideal + self.temperature_tolerance > 60:
            raise ValueError("El límite máximo de temperatura no puede superar 60 °C")
        if self.humidity_ideal - self.humidity_tolerance < 0:
            raise ValueError("El límite mínimo de humedad no puede ser menor a 0 %")
        if self.humidity_ideal + self.humidity_tolerance > 100:
            raise ValueError("El límite máximo de humedad no puede superar 100 %")
        return self
