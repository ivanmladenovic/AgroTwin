"""Additive map editor geometry fields (isolated; no destructive changes).

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2026-10-12 08:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "x3y4z5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "w2x3y4z5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parcels",
        sa.Column("map_layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "orchard_rows",
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "orchard_rows",
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("orchard_rows", "segment_count")
    op.drop_column("orchard_rows", "geometry")
    op.drop_column("parcels", "map_layout")
