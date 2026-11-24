"""Asistente IA: título local de conversación (B3).

Revision ID: 0014_ai_conversation_title
Revises: 0013_ai_resilience
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_ai_conversation_title"
down_revision: str | None = "0013_ai_resilience"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_conversations",
        sa.Column("title", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_conversations", "title")
