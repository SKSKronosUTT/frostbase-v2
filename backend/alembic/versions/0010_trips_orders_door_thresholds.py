"""Viajes, órdenes, bitácora, eventos de puerta y umbrales por camión (G1)

Revision ID: 0010_trips_orders_door
Revises: 0009_route_driver_schedule
Create Date: 2026-11-20

- ``trips``: un solo viaje ``in_progress`` por conductor y por camión
  (índices únicos parciales). ``route_id`` es ``SET NULL`` para conservar el
  historial si la ruta se elimina.
- ``trip_orders``: congelan los datos de la parada; una orden ``failed`` exige
  ``failure_reason`` no vacío (CHECK, texto libre obligatorio de G0).
- ``trip_logs``: bitácora de eventos de viaje y órdenes con ``created_at``.
- ``door_events``: idempotentes por ``(device_id, event_time)``; los eventos
  abiertos sin evaluar quedan indexados para el escaneo del watcher (periodo
  de gracia). ``alerts`` gana acuse (``acknowledged_*``) y ``trip_id``.
- ``truck_threshold_overrides``: umbrales por camión con fallback a los
  valores globales (H3). ``settings.door_open_grace_seconds``: gracia global
  configurable, por defecto 30 s (G0).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_trips_orders_door"
down_revision: str | None = "0009_route_driver_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "driver_id",
            sa.Integer(),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "truck_id",
            sa.Integer(),
            sa.ForeignKey("trucks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_trips_active_driver",
        "trips",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text("state = 'in_progress'"),
    )
    op.create_index(
        "uq_trips_active_truck",
        "trips",
        ["truck_id"],
        unique=True,
        postgresql_where=sa.text("state = 'in_progress'"),
    )
    op.create_index(
        "ix_trips_driver_started",
        "trips",
        ["driver_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "trip_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "delivery_point_id",
            sa.Integer(),
            sa.ForeignKey("delivery_points.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "store_id",
            sa.Integer(),
            sa.ForeignKey("stores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "state <> 'failed' OR (failure_reason IS NOT NULL "
            "AND btrim(failure_reason) <> '')",
            name="ck_trip_orders_failed_reason",
        ),
    )
    op.create_index(
        "uq_trip_orders_trip_index",
        "trip_orders",
        ["trip_id", "order_index"],
        unique=True,
    )

    op.create_table(
        "trip_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trips.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("trip_orders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "actor_admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_driver_id",
            sa.Integer(),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_trip_logs_trip_created",
        "trip_logs",
        ["trip_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "door_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "device_id",
            sa.Integer(),
            sa.ForeignKey("devices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "truck_id",
            sa.Integer(),
            sa.ForeignKey("trucks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_open", sa.Boolean(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "alert_id",
            sa.Integer(),
            sa.ForeignKey("alerts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_door_events_device_time",
        "door_events",
        ["device_id", "event_time"],
        unique=True,
    )
    op.create_index(
        "ix_door_events_pending",
        "door_events",
        [sa.text("event_time")],
        postgresql_where=sa.text("evaluated_at IS NULL AND is_open = true"),
    )

    op.add_column(
        "alerts",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "acknowledged_by",
            sa.Integer(),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "trip_id",
            sa.Integer(),
            sa.ForeignKey("trips.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_alerts_trip_started", "alerts", ["trip_id", "started_at"])

    op.create_table(
        "truck_threshold_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "truck_id",
            sa.Integer(),
            sa.ForeignKey("trucks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("temperature_ideal", sa.Float(), nullable=True),
        sa.Column("temperature_tolerance", sa.Float(), nullable=True),
        sa.Column("humidity_ideal", sa.Float(), nullable=True),
        sa.Column("humidity_tolerance", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_truck_threshold_overrides_truck",
        "truck_threshold_overrides",
        ["truck_id"],
        unique=True,
    )

    op.add_column(
        "settings",
        sa.Column(
            "door_open_grace_seconds",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "door_open_grace_seconds")
    op.drop_index(
        "uq_truck_threshold_overrides_truck", table_name="truck_threshold_overrides"
    )
    op.drop_table("truck_threshold_overrides")
    op.drop_index("ix_alerts_trip_started", table_name="alerts")
    op.drop_column("alerts", "trip_id")
    op.drop_column("alerts", "acknowledged_by")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_index("ix_door_events_pending", table_name="door_events")
    op.drop_index("uq_door_events_device_time", table_name="door_events")
    op.drop_table("door_events")
    op.drop_index("ix_trip_logs_trip_created", table_name="trip_logs")
    op.drop_table("trip_logs")
    op.drop_index("uq_trip_orders_trip_index", table_name="trip_orders")
    op.drop_table("trip_orders")
    op.drop_index("ix_trips_driver_started", table_name="trips")
    op.drop_index("uq_trips_active_truck", table_name="trips")
    op.drop_index("uq_trips_active_driver", table_name="trips")
    op.drop_table("trips")
