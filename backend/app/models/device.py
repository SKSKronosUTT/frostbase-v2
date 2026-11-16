from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.reading import Reading
    from app.models.truck import Truck


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("trucks.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    truck: Mapped["Truck | None"] = relationship(
        back_populates="device", foreign_keys=[truck_id], lazy="selectin"
    )
    readings: Mapped[list["Reading"]] = relationship(back_populates="device")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="device")
