"""planting varieties and row variety

Revision ID: a1b2c3d4e506
Revises: e5c1f9a2b406
Create Date: 2026-09-14 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e506"
down_revision: Union[str, Sequence[str], None] = "e5c1f9a2b406"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "parcels",
        sa.Column("varieties", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )
    op.add_column("orchard_rows", sa.Column("variety", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("orchard_rows", "variety")
    op.drop_column("parcels", "varieties")
