"""Catálogo de tiendas/destinos de entrega (G1).

Las paradas de una ruta siguen siendo ``delivery_points`` (con dirección y
coordenadas congeladas por ruta); ``stores`` permite reutilizar destinos entre
rutas y enlazarlos con ``delivery_points.store_id``.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.utils.time import utcnow


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (Index("ix_stores_name_lower", text("lower(name)")),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
