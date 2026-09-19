"""activity line items and extra rows

Revision ID: c4d5e6f70819
Revises: b2c3d4e5f607
Create Date: 2026-09-14 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f70819"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f607"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("line_items", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )
    op.add_column(
        "activities",
        sa.Column("extra_row_ids", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("activities", "extra_row_ids")
    op.drop_column("activities", "line_items")
