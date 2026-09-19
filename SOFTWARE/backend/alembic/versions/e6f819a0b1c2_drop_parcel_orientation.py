"""drop parcel orientation

Revision ID: e6f819a0b1c2
Revises: d5e6f70819a0
Create Date: 2026-09-14 13:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e6f819a0b1c2"
down_revision: Union[str, Sequence[str], None] = "d5e6f70819a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("parcels", "orientation_degrees")


def downgrade() -> None:
    op.add_column(
        "parcels",
        sa.Column("orientation_degrees", sa.Numeric(precision=6, scale=2), server_default="0", nullable=False),
    )
