"""Conductores, identidades de login y asignación de camiones (G1)

Revision ID: 0008_drivers_and_assignments
Revises: 0007_route_geometry_status
Create Date: 2026-11-20

- ``drivers``: credenciales con hash Argon2, baja lógica (``is_active``),
  ``must_change_password`` y ``token_version`` para revocación inmediata.
- ``login_identities``: garantiza a nivel de base de datos que un correo no
  exista a la vez como administrador y como conductor (los servicios la
  mantienen en la misma transacción que crean/reactivan cuentas).
- ``driver_truck_assignments``: historial de relevo conductor-camión con una
  sola asignación activa por conductor y por camión (índices únicos parciales).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_drivers_and_assignments"
down_revision: str | None = "0007_route_geometry_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("middle_name", sa.String(length=80), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("birthdate", sa.Date(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
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
        "uq_drivers_email_lower",
        "drivers",
        [sa.text("lower(email)")],
        unique=True,
    )
    op.create_index("ix_drivers_active", "drivers", ["is_active"])

    op.create_table(
        "login_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("account_type", sa.String(length=10), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_login_identities_email"),
    )
    op.create_index(
        "ix_login_identities_account",
        "login_identities",
        ["account_type", "account_id"],
    )

    op.create_table(
        "driver_truck_assignments",
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
            "assigned_by",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_assignment_active_driver",
        "driver_truck_assignments",
        ["driver_id"],
        unique=True,
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    op.create_index(
        "uq_assignment_active_truck",
        "driver_truck_assignments",
        ["truck_id"],
        unique=True,
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    op.create_index(
        "ix_assignments_driver_history",
        "driver_truck_assignments",
        ["driver_id", sa.text("assigned_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assignments_driver_history", table_name="driver_truck_assignments"
    )
    op.drop_index("uq_assignment_active_truck", table_name="driver_truck_assignments")
    op.drop_index("uq_assignment_active_driver", table_name="driver_truck_assignments")
    op.drop_table("driver_truck_assignments")
    op.drop_index("ix_login_identities_account", table_name="login_identities")
    op.drop_table("login_identities")
    op.drop_index("ix_drivers_active", table_name="drivers")
    op.drop_index("uq_drivers_email_lower", table_name="drivers")
    op.drop_table("drivers")
