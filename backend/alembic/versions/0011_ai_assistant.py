"""Asistente IA: cuota y conversaciones (A1).

Revision ID: 0011_ai_assistant
Revises: 0010_trips_orders_door
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_ai_assistant"
down_revision: str | None = "0010_trips_orders_door"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "uq_ai_usage_admin_day",
        "ai_usage",
        ["admin_id", "day"],
        unique=True,
    )

    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_session", sa.String(length=100), nullable=True),
        sa.Column("last_seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_ai_conversations_admin",
        "ai_conversations",
        ["admin_id", "last_used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_conversations_admin", table_name="ai_conversations")
    op.drop_table("ai_conversations")
    op.drop_index("uq_ai_usage_admin_day", table_name="ai_usage")
    op.drop_table("ai_usage")
