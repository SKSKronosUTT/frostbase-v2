"""Asistente IA: auditoría de uso (A5).

Revision ID: 0012_ai_audit
Revises: 0011_ai_assistant
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_ai_audit"
down_revision: str | None = "0011_ai_assistant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("detail", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_audit_created", "ai_audit", ["created_at"])
    op.create_index("ix_ai_audit_admin_created", "ai_audit", ["admin_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_audit_admin_created", table_name="ai_audit")
    op.drop_index("ix_ai_audit_created", table_name="ai_audit")
    op.drop_table("ai_audit")
