"""Estado de geometría de rutas (cálculo asíncrono opcional)

Revision ID: 0007_route_geometry_status
Revises: 0006_trucks_plate_partial_unique
Create Date: 2026-11-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_route_geometry_status"
down_revision: Union[str, None] = "0006_trucks_plate_partial_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routes",
        sa.Column(
            "geometry_status",
            sa.String(length=20),
            nullable=False,
            server_default="ready",
        ),
    )


def downgrade() -> None:
    op.drop_column("routes", "geometry_status")
