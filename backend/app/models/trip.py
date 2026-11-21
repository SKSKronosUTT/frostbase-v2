"""Viajes, órdenes de entrega y bitácora del módulo de conductores (G1).

Reglas de integridad importantes:

- Un solo viaje ``in_progress`` por conductor y por camión (índices únicos
  parciales).
- Las órdenes congelan nombre, dirección y coordenadas de la parada original
  para conservar el historial aunque la ruta cambie después.
- Una orden ``failed`` exige ``failure_reason`` (CHECK), con texto libre
  obligatorio según la decisión de G0.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.driver import Driver
    from app.models.route import Route
    from app.models.truck import Truck

TRIP_STATE_IN_PROGRESS = "in_progress"
TRIP_STATE_COMPLETED = "completed"

ORDER_STATE_PENDING = "pending"
ORDER_STATE_IN_DELIVERY = "in_delivery"
ORDER_STATE_DELIVERED = "delivered"
ORDER_STATE_FAILED = "failed"


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        Index(
            "uq_trips_active_driver",
            "driver_id",
            unique=True,
            postgresql_where=text("state = 'in_progress'"),
        ),
        Index(
            "uq_trips_active_truck",
            "truck_id",
            unique=True,
            postgresql_where=text("state = 'in_progress'"),
        ),
        Index(
            "ix_trips_driver_started",
            "driver_id",
            text("started_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False
    )
    truck_id: Mapped[int] = mapped_column(
        ForeignKey("trucks.id", ondelete="RESTRICT"), nullable=False
    )
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str] = mapped_column(
        String(20), default=TRIP_STATE_IN_PROGRESS, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    driver: Mapped["Driver"] = relationship()
    truck: Mapped["Truck"] = relationship()
    route: Mapped["Route | None"] = relationship()
    orders: Mapped[list["TripOrder"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripOrder.order_index",
    )
    logs: Mapped[list["TripLog"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )


class TripOrder(Base):
    __tablename__ = "trip_orders"
    __table_args__ = (
        CheckConstraint(
            "state <> 'failed' OR (failure_reason IS NOT NULL "
            "AND btrim(failure_reason) <> '')",
            name="ck_trip_orders_failed_reason",
        ),
        Index("uq_trip_orders_trip_index", "trip_id", "order_index", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    delivery_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_points.id", ondelete="SET NULL"), nullable=True
    )
    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), nullable=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), default=ORDER_STATE_PENDING, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    trip: Mapped["Trip"] = relationship(back_populates="orders")


class TripLog(Base):
    """Bitácora de eventos de viaje y de órdenes (una sola tabla, H10)."""

    __tablename__ = "trip_logs"
    __table_args__ = (
        Index("ix_trip_logs_trip_created", "trip_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(
        ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("trip_orders.id", ondelete="CASCADE"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"), nullable=True
    )
    actor_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    trip: Mapped["Trip"] = relationship(back_populates="logs")
