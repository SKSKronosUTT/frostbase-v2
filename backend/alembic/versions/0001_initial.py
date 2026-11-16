"""Esquema inicial de FrostBase

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("theme", sa.String(length=10), nullable=False, server_default="light"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admins_username", "admins", ["username"], unique=True)
    op.create_index("ix_admins_email", "admins", ["email"], unique=True)

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("geometry", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="activa"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("temperature_ideal", sa.Float(), nullable=False, server_default="-2"),
        sa.Column("temperature_tolerance", sa.Float(), nullable=False, server_default="3"),
        sa.Column("humidity_ideal", sa.Float(), nullable=False, server_default="80"),
        sa.Column("humidity_tolerance", sa.Float(), nullable=False, server_default="5"),
        sa.Column(
            "offline_timeout_seconds", sa.Integer(), nullable=False, server_default="60"
        ),
        sa.Column("weather_city", sa.String(length=120), nullable=False, server_default="Tijuana"),
        sa.Column("weather_latitude", sa.Float(), nullable=False, server_default="32.5149"),
        sa.Column("weather_longitude", sa.Float(), nullable=False, server_default="-117.0382"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "trucks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("plate", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="disponible"),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_trucks_plate", "trucks", ["plate"], unique=True)
    op.create_index("ix_trucks_route_id", "trucks", ["route_id"], unique=True)

    op.create_table(
        "delivery_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_delivery_points_route_id", "delivery_points", ["route_id"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.String(length=100), nullable=False),
        sa.Column("truck_id", sa.Integer(), nullable=True),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_devices_device_id", "devices", ["device_id"], unique=True)
    op.create_index("ix_devices_truck_id", "devices", ["truck_id"], unique=True)

    op.create_table(
        "readings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("truck_id", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("humidity", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reading_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_readings_device_id", "readings", ["device_id"])
    op.create_index("ix_readings_truck_id", "readings", ["truck_id"])
    op.create_index("ix_readings_truck_time", "readings", ["truck_id", "reading_timestamp"])
    op.create_index("ix_readings_device_time", "readings", ["device_id", "reading_timestamp"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("truck_id", sa.Integer(), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="activa"),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_alerts_truck_id", "alerts", ["truck_id"])
    op.create_index("ix_alerts_device_id", "alerts", ["device_id"])
    op.create_index("ix_alerts_status_started", "alerts", ["status", "started_at"])
    op.create_index(
        "uq_alerts_active_device_type",
        "alerts",
        ["device_id", "alert_type"],
        unique=True,
        postgresql_where=sa.text("status = 'activa'"),
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("readings")
    op.drop_table("devices")
    op.drop_table("delivery_points")
    op.drop_table("trucks")
    op.drop_table("settings")
    op.drop_table("routes")
    op.drop_table("admins")
