"""Unicidad de placa compatible con borrado lógico

Revision ID: 0006_trucks_plate_partial_unique
Revises: 0005_perf_indexes
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_trucks_plate_partial_unique"
down_revision: str | None = "0005_perf_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_trucks_plate", table_name="trucks")
    op.create_index(
        "uq_trucks_plate_active",
        "trucks",
        ["plate"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_trucks_plate_active", table_name="trucks")
    op.create_index("ix_trucks_plate", "trucks", ["plate"], unique=True)
