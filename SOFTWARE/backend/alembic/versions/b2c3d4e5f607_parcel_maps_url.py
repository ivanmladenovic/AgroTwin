"""parcel google maps url

Revision ID: b2c3d4e5f607
Revises: a1b2c3d4e506
Create Date: 2026-09-14 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f607"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e506"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parcels", sa.Column("maps_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    op.drop_column("parcels", "maps_url")
