"""Esquema de claves de dispositivo: Argon2 legacy + HMAC

Revision ID: 0003_device_key_scheme
Revises: 0002_admin_auth_policy
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_device_key_scheme"
down_revision: str | None = "0002_admin_auth_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column(
            "key_scheme",
            sa.String(length=16),
            nullable=False,
            server_default="argon2",
        ),
    )


def downgrade() -> None:
    op.drop_column("devices", "key_scheme")
