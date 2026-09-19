"""harvest events for parcel production

Revision ID: a8b9c0d1e2f3
Revises: f7a920b1c3d4
Create Date: 2026-09-15 09:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a920b1c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE attachment_entity_type ADD VALUE IF NOT EXISTS 'harvest_event'")
    quality = postgresql.ENUM("premium", "standard", "lower", "other", name="harvest_quality_category")
    quality.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "harvest_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "scope_type",
            postgresql.ENUM("farm", "parcel", "row", "tree", name="scope_type", create_type=False),
            nullable=False,
        ),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tree_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("harvested_on", sa.Date(), nullable=False),
        sa.Column("gross_quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("loss_quantity", sa.Numeric(precision=12, scale=3), server_default="0", nullable=False),
        sa.Column(
            "net_quantity",
            sa.Numeric(precision=12, scale=3),
            sa.Computed("gross_quantity - loss_quantity", persisted=True),
            nullable=False,
        ),
        sa.Column("unit", sa.String(length=32), server_default="kg", nullable=False),
        sa.Column("moisture_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "quality_category",
            postgresql.ENUM("premium", "standard", "lower", "other", name="harvest_quality_category", create_type=False),
            nullable=True,
        ),
        sa.Column("damaged_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("empty_nuts_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("foreign_material_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("size_or_caliber", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            """
            (scope_type = 'farm' AND parcel_id IS NULL AND row_id IS NULL AND tree_id IS NULL)
            OR (scope_type = 'parcel' AND parcel_id IS NOT NULL AND row_id IS NULL AND tree_id IS NULL)
            OR (scope_type = 'row' AND parcel_id IS NOT NULL AND row_id IS NOT NULL AND tree_id IS NULL)
            OR (scope_type = 'tree' AND parcel_id IS NOT NULL AND row_id IS NOT NULL AND tree_id IS NOT NULL)
            """,
            name="ck_harvest_events_scope_matches_ids",
        ),
        sa.CheckConstraint("gross_quantity > 0", name="ck_harvest_events_gross_positive"),
        sa.CheckConstraint("loss_quantity >= 0", name="ck_harvest_events_loss_nonnegative"),
        sa.CheckConstraint("loss_quantity <= gross_quantity", name="ck_harvest_events_loss_lte_gross"),
        sa.CheckConstraint(
            "moisture_percent IS NULL OR (moisture_percent >= 0 AND moisture_percent <= 100)",
            name="ck_harvest_events_moisture",
        ),
        sa.CheckConstraint(
            "damaged_percent IS NULL OR (damaged_percent >= 0 AND damaged_percent <= 100)",
            name="ck_harvest_events_damaged",
        ),
        sa.CheckConstraint(
            "empty_nuts_percent IS NULL OR (empty_nuts_percent >= 0 AND empty_nuts_percent <= 100)",
            name="ck_harvest_events_empty_nuts",
        ),
        sa.CheckConstraint(
            "foreign_material_percent IS NULL OR (foreign_material_percent >= 0 AND foreign_material_percent <= 100)",
            name="ck_harvest_events_foreign_material",
        ),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["row_id"], ["orchard_rows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tree_id"], ["trees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_harvest_events_farm_id"), "harvest_events", ["farm_id"], unique=False)
    op.create_index(op.f("ix_harvest_events_parcel_id"), "harvest_events", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_harvest_events_row_id"), "harvest_events", ["row_id"], unique=False)
    op.create_index(op.f("ix_harvest_events_tree_id"), "harvest_events", ["tree_id"], unique=False)
    op.create_index(op.f("ix_harvest_events_scope_type"), "harvest_events", ["scope_type"], unique=False)
    op.create_index(op.f("ix_harvest_events_harvested_on"), "harvest_events", ["harvested_on"], unique=False)
    op.create_index(op.f("ix_harvest_events_quality_category"), "harvest_events", ["quality_category"], unique=False)
    op.create_index(op.f("ix_harvest_events_activity_id"), "harvest_events", ["activity_id"], unique=False)
    op.create_index("ix_harvest_events_parcel_harvested_on", "harvest_events", ["parcel_id", "harvested_on"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_harvest_events_parcel_harvested_on", table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_activity_id"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_quality_category"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_harvested_on"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_scope_type"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_tree_id"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_row_id"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_parcel_id"), table_name="harvest_events")
    op.drop_index(op.f("ix_harvest_events_farm_id"), table_name="harvest_events")
    op.drop_table("harvest_events")
    postgresql.ENUM(name="harvest_quality_category").drop(op.get_bind(), checkfirst=True)
