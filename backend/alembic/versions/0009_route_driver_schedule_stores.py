"""Propiedad de rutas por conductor, calendario semanal y tiendas (G1)

Revision ID: 0009_route_driver_schedule
Revises: 0008_drivers_and_assignments
Create Date: 2026-11-20

- ``routes.assigned_driver_id``: la ruta pertenece al conductor (decisión G0).
  ``trucks.route_id`` se conserva durante la transición; el administrador
  reasignará explícitamente los vínculos existentes antes de retirarlo.
- ``route_delivery_days``: calendario semanal (0=domingo … 6=sábado) con una
  sola ruta activa por conductor y día. ``driver_id`` va desnormalizado para
  poder exigirlo con un índice único; los servicios lo mantienen coherente
  con ``routes.assigned_driver_id`` en la misma transacción.
- ``stores`` + ``delivery_points.store_id``: catálogo de destinos reutilizable;
  las paradas conservan su copia de nombre/dirección/coordenadas.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_route_driver_schedule"
down_revision: str | None = "0008_drivers_and_assignments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "routes",
        sa.Column(
            "assigned_driver_id",
            sa.Integer(),
            sa.ForeignKey("drivers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_routes_assigned_driver",
        "routes",
        ["assigned_driver_id"],
    )

    op.create_table(
        "route_delivery_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            sa.Integer(),
            sa.ForeignKey("drivers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "uq_route_delivery_days_route_weekday",
        "route_delivery_days",
        ["route_id", "weekday"],
        unique=True,
    )
    op.create_index(
        "uq_route_delivery_days_driver_weekday",
        "route_delivery_days",
        ["driver_id", "weekday"],
        unique=True,
    )

    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
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
        "ix_stores_name_lower",
        "stores",
        [sa.text("lower(name)")],
    )

    op.add_column(
        "delivery_points",
        sa.Column(
            "store_id",
            sa.Integer(),
            sa.ForeignKey("stores.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_delivery_points_store", "delivery_points", ["store_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_points_store", table_name="delivery_points")
    op.drop_column("delivery_points", "store_id")
    op.drop_index("ix_stores_name_lower", table_name="stores")
    op.drop_table("stores")
    op.drop_index(
        "uq_route_delivery_days_driver_weekday", table_name="route_delivery_days"
    )
    op.drop_index(
        "uq_route_delivery_days_route_weekday", table_name="route_delivery_days"
    )
    op.drop_table("route_delivery_days")
    op.drop_index("ix_routes_assigned_driver", table_name="routes")
    op.drop_column("routes", "assigned_driver_id")
