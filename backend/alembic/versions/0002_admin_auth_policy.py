"""Política de autenticación de administradores

Revision ID: 0002_admin_auth_policy
Revises: 0001_initial
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_admin_auth_policy"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "admins",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Rotación única forzada para todos los administradores existentes.
    op.execute("UPDATE admins SET must_change_password = true")


def downgrade() -> None:
    op.drop_column("admins", "token_version")
    op.drop_column("admins", "must_change_password")
