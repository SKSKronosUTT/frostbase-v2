from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.truck import Truck


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index(
            "uq_alerts_active_device_type",
            "device_id",
            "alert_type",
            unique=True,
            postgresql_where=text("status = 'activa'"),
        ),
        Index("ix_alerts_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("trucks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="activa", nullable=False)

    truck: Mapped["Truck | None"] = relationship(back_populates="alerts", lazy="selectin")
    device: Mapped["Device | None"] = relationship(back_populates="alerts", lazy="selectin")
