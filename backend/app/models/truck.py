from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.device import Device
    from app.models.reading import Reading
    from app.models.route import Route


class Truck(Base):
    __tablename__ = "trucks"
    __table_args__ = (
        Index(
            "uq_trucks_plate_active",
            "plate",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    plate: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="disponible", nullable=False)
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    route: Mapped["Route | None"] = relationship(
        back_populates="truck", foreign_keys=[route_id], lazy="selectin"
    )
    device: Mapped["Device | None"] = relationship(
        back_populates="truck", uselist=False, lazy="selectin"
    )
    readings: Mapped[list["Reading"]] = relationship(back_populates="truck")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="truck")
