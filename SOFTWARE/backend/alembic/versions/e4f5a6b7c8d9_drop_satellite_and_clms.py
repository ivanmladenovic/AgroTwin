"""drop unused sentinel-2 and clms tables

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-20 13:50:00.000000

Keeps parcels.altitude and parcels.boundary (parcel location fields).
Drops Sentinel-2 / CLMS observation caches that are no longer used.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    "evapotranspiration_query_caches",
    "evapotranspiration_observations",
    "soil_moisture_query_caches",
    "soil_moisture_observations",
    "satellite_query_caches",
    "satellite_observations",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    for table in _TABLES:
        if table in existing:
            op.drop_table(table)


def downgrade() -> None:
    # Intentionally empty: Sentinel-2 / CLMS modules were removed.
    return
