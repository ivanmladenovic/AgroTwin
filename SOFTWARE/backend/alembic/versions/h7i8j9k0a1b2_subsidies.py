"""subsidies received against orchard costs

Revision ID: h7i8j9k0a1b2
Revises: g6h7i8j9k0a1
Create Date: 2026-09-22 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "h7i8j9k0a1b2"
down_revision: Union[str, Sequence[str], None] = "g6h7i8j9k0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subsidies",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("subsidy_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="EUR", nullable=False),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("total_cost > 0", name="ck_subsidies_total_cost_positive"),
        sa.CheckConstraint("subsidy_amount >= 0", name="ck_subsidies_amount_nonnegative"),
        sa.CheckConstraint("subsidy_amount <= total_cost", name="ck_subsidies_amount_lte_total"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subsidies_farm_id"), "subsidies", ["farm_id"], unique=False)
    op.create_index(op.f("ix_subsidies_parcel_id"), "subsidies", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_subsidies_received_on"), "subsidies", ["received_on"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_subsidies_received_on"), table_name="subsidies")
    op.drop_index(op.f("ix_subsidies_parcel_id"), table_name="subsidies")
    op.drop_index(op.f("ix_subsidies_farm_id"), table_name="subsidies")
    op.drop_table("subsidies")
