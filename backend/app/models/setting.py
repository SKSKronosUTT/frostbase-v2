from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.time import utcnow


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    temperature_ideal: Mapped[float] = mapped_column(
        Float, default=-2.0, nullable=False
    )
    temperature_tolerance: Mapped[float] = mapped_column(
        Float, default=3.0, nullable=False
    )
    humidity_ideal: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    humidity_tolerance: Mapped[float] = mapped_column(
        Float, default=5.0, nullable=False
    )
    offline_timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    weather_city: Mapped[str] = mapped_column(
        String(120), default="Tijuana", nullable=False
    )
    weather_latitude: Mapped[float] = mapped_column(
        Float, default=32.5149, nullable=False
    )
    weather_longitude: Mapped[float] = mapped_column(
        Float, default=-117.0382, nullable=False
    )
    door_open_grace_seconds: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    @property
    def temperature_min(self) -> float:
        return round(self.temperature_ideal - self.temperature_tolerance, 2)

    @property
    def temperature_max(self) -> float:
        return round(self.temperature_ideal + self.temperature_tolerance, 2)

    @property
    def humidity_min(self) -> float:
        return round(self.humidity_ideal - self.humidity_tolerance, 2)

    @property
    def humidity_max(self) -> float:
        return round(self.humidity_ideal + self.humidity_tolerance, 2)
