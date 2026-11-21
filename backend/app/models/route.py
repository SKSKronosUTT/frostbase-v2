from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.driver import Driver
    from app.models.truck import Truck


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    geometry: Mapped[list | None] = mapped_column(JSON, nullable=True)
    geometry_status: Mapped[str] = mapped_column(
        String(20), default="ready", server_default="ready", nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="activa", nullable=False)
    assigned_driver_id: Mapped[int | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    points: Mapped[list["DeliveryPoint"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="DeliveryPoint.order_index",
        lazy="selectin",
    )
    truck: Mapped["Truck | None"] = relationship(
        back_populates="route", uselist=False, foreign_keys="Truck.route_id"
    )
    assigned_driver: Mapped["Driver | None"] = relationship()
    delivery_days: Mapped[list["RouteDeliveryDay"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteDeliveryDay.weekday",
    )


class RouteDeliveryDay(Base):
    """Calendario semanal de la ruta (0=domingo … 6=sábado).

    ``driver_id`` está desnormalizado respecto de ``routes.assigned_driver_id``
    para poder exigir en la base de datos una sola ruta activa por conductor y
    día. Los servicios validan la coherencia en la misma transacción.
    """

    __tablename__ = "route_delivery_days"
    __table_args__ = (
        Index(
            "uq_route_delivery_days_route_weekday",
            "route_id",
            "weekday",
            unique=True,
        ),
        Index(
            "uq_route_delivery_days_driver_weekday",
            "driver_id",
            "weekday",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    route: Mapped["Route"] = relationship(back_populates="delivery_days")
    driver: Mapped["Driver"] = relationship()


class DeliveryPoint(Base):
    __tablename__ = "delivery_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int | None] = mapped_column(
        ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    route: Mapped[Route] = relationship(back_populates="points")
