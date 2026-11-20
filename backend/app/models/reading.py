from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.truck import Truck


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        Index("ix_readings_truck_time", "truck_id", "reading_timestamp"),
        Index("ix_readings_device_time", "device_id", "reading_timestamp"),
        Index(
            "ix_readings_received_at",
            "received_at",
            postgresql_ops={"received_at": "DESC"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("trucks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    reading_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    device: Mapped["Device"] = relationship(back_populates="readings")
    truck: Mapped["Truck | None"] = relationship(back_populates="readings")
