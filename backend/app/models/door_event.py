"""Eventos de puerta del contenedor (G1).

El ESP32 envía un JSON inmediato cada vez que cambia el estado de la puerta.
Todo evento se registra (idempotente por ``(device_id, event_time)``). La
alerta ``puerta`` solo se crea si, al vencer el periodo de gracia configurable
(``settings.door_open_grace_seconds``, por defecto 30 s), la puerta sigue
abierta durante un viaje ``in_progress`` y sin una orden ``in_delivery``.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow


class DoorEvent(Base):
    __tablename__ = "door_events"
    __table_args__ = (
        Index("uq_door_events_device_time", "device_id", "event_time", unique=True),
        Index(
            "ix_door_events_pending",
            text("event_time"),
            postgresql_where=text("evaluated_at IS NULL AND is_open = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False
    )
    truck_id: Mapped[int | None] = mapped_column(
        ForeignKey("trucks.id", ondelete="SET NULL"), nullable=True
    )
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )

    device = relationship("Device")
    truck = relationship("Truck")
