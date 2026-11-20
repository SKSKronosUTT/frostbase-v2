"""Deduplicación de lecturas e índice único de idempotencia

Revision ID: 0004_readings_idempotency
Revises: 0003_device_key_scheme
Create Date: 2026-11-19

La migración elimina duplicados históricos conservando MIN(id) por
(device_id, reading_timestamp) y crea el índice único que hace idempotente la
ingesta. Antes de aplicarla en producción, haga un respaldo y ejecute
``python -m scripts.dedupe_readings --dry-run``.
"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_readings_idempotency"
down_revision: str | None = "0003_device_key_scheme"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

_DUPLICATE_ROWS_SQL = sa.text(
    """
    SELECT COALESCE(sum(n - 1), 0)
    FROM (
        SELECT count(*) AS n
        FROM readings
        GROUP BY device_id, reading_timestamp
        HAVING count(*) > 1
    ) AS duplicates
    """
)

_DELETE_DUPLICATES_SQL = sa.text(
    """
    DELETE FROM readings a
    USING readings b
    WHERE a.device_id = b.device_id
      AND a.reading_timestamp = b.reading_timestamp
      AND a.id > b.id
    """
)


def upgrade() -> None:
    connection = op.get_bind()
    rows_to_delete = int(connection.execute(_DUPLICATE_ROWS_SQL).scalar() or 0)
    logger.info(
        "0004_readings_idempotency: se eliminarán %s lecturas duplicadas",
        rows_to_delete,
    )
    if rows_to_delete:
        connection.execute(_DELETE_DUPLICATES_SQL)
    op.create_index(
        "uq_readings_device_timestamp",
        "readings",
        ["device_id", "reading_timestamp"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_readings_device_timestamp", table_name="readings")
