"""Índices de rendimiento para dashboard y alertas

Revision ID: 0005_perf_indexes
Revises: 0004_readings_idempotency
Create Date: 2026-11-19

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_perf_indexes"
down_revision: str | None = "0004_readings_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_readings_received_at",
        "readings",
        ["received_at"],
        postgresql_ops={"received_at": "DESC"},
    )
    op.create_index(
        "ix_alerts_truck_status",
        "alerts",
        ["truck_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_truck_status", table_name="alerts")
    op.drop_index("ix_readings_received_at", table_name="readings")
