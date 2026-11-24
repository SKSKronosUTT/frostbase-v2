"""Asistente IA: resiliencia (boot_id y cortacircuito) (B1).

Revision ID: 0013_ai_resilience
Revises: 0012_ai_audit
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_ai_resilience"
down_revision: str | None = "0012_ai_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("agent_boot_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_ai_conversations_last_used", "ai_conversations", ["last_used_at"]
    )
    op.create_table(
        "ai_breaker",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_breaker")
    op.drop_index("ix_ai_conversations_last_used", table_name="ai_conversations")
    op.drop_column("ai_conversations", "agent_boot_id")
