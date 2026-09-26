"""soil lab analyses attached to activities

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-20 14:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "soil_lab_analyses",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tree_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sampled_on", sa.Date(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tree_id"], ["trees.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_soil_lab_analyses_activity_id"), "soil_lab_analyses", ["activity_id"], unique=False)
    op.create_index(op.f("ix_soil_lab_analyses_farm_id"), "soil_lab_analyses", ["farm_id"], unique=False)
    op.create_index(op.f("ix_soil_lab_analyses_parcel_id"), "soil_lab_analyses", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_soil_lab_analyses_tree_id"), "soil_lab_analyses", ["tree_id"], unique=False)
    op.create_index(op.f("ix_soil_lab_analyses_sampled_on"), "soil_lab_analyses", ["sampled_on"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_soil_lab_analyses_sampled_on"), table_name="soil_lab_analyses")
    op.drop_index(op.f("ix_soil_lab_analyses_tree_id"), table_name="soil_lab_analyses")
    op.drop_index(op.f("ix_soil_lab_analyses_parcel_id"), table_name="soil_lab_analyses")
    op.drop_index(op.f("ix_soil_lab_analyses_farm_id"), table_name="soil_lab_analyses")
    op.drop_index(op.f("ix_soil_lab_analyses_activity_id"), table_name="soil_lab_analyses")
    op.drop_table("soil_lab_analyses")
