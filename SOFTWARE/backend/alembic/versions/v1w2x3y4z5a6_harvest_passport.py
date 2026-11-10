"""harvest lots, passport snapshots, farm public fields

Revision ID: v1w2x3y4z5a6
Revises: u0v1w2x3y4z5
Create Date: 2026-10-08 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "v1w2x3y4z5a6"
down_revision: Union[str, Sequence[str], None] = "u0v1w2x3y4z5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    passport_status = postgresql.ENUM(
        "draft", "published", "finalized", "revoked", name="passport_status", create_type=False
    )
    postgresql.ENUM(
        "draft", "published", "finalized", "revoked", name="passport_status"
    ).create(op.get_bind(), checkfirst=True)

    op.add_column("farms", sa.Column("country", sa.String(length=128), nullable=True))
    op.add_column("farms", sa.Column("public_producer_name", sa.String(length=255), nullable=True))
    op.add_column("farms", sa.Column("logo_url", sa.String(length=512), nullable=True))
    op.execute("UPDATE farms SET country = 'Srbija' WHERE country IS NULL")

    op.create_table(
        "harvest_lot_sequences",
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("year"),
    )

    op.create_table(
        "harvest_lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("harvest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lot_number", sa.String(length=32), nullable=False),
        sa.Column("harvest_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="kg"),
        sa.Column("crop", sa.String(length=128), nullable=False, server_default="Lesnik"),
        sa.Column("variety", sa.String(length=128), nullable=True),
        sa.Column("passport_token", sa.String(length=64), nullable=False),
        sa.Column("passport_status", passport_status, nullable=False),
        sa.Column("visibility", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("allow_indexing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("passport_version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["harvest_id"], ["harvest_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lot_number", name="uq_harvest_lots_lot_number"),
        sa.UniqueConstraint("passport_token"),
    )
    op.create_index("ix_harvest_lots_farm_id", "harvest_lots", ["farm_id"])
    op.create_index("ix_harvest_lots_parcel_id", "harvest_lots", ["parcel_id"])
    op.create_index("ix_harvest_lots_harvest_id", "harvest_lots", ["harvest_id"])
    op.create_index("ix_harvest_lots_lot_number", "harvest_lots", ["lot_number"])
    op.create_index("ix_harvest_lots_harvest_date", "harvest_lots", ["harvest_date"])
    op.create_index("ix_harvest_lots_passport_token", "harvest_lots", ["passport_token"])
    op.create_index("ix_harvest_lots_passport_status", "harvest_lots", ["passport_status"])

    op.create_table(
        "passport_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("harvest_lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("passport_version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["harvest_lot_id"], ["harvest_lots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("harvest_lot_id", "version", name="uq_passport_snapshots_lot_version"),
    )
    op.create_index("ix_passport_snapshots_harvest_lot_id", "passport_snapshots", ["harvest_lot_id"])


def downgrade() -> None:
    op.drop_index("ix_passport_snapshots_harvest_lot_id", table_name="passport_snapshots")
    op.drop_table("passport_snapshots")
    op.drop_index("ix_harvest_lots_passport_status", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_passport_token", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_harvest_date", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_lot_number", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_harvest_id", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_parcel_id", table_name="harvest_lots")
    op.drop_index("ix_harvest_lots_farm_id", table_name="harvest_lots")
    op.drop_table("harvest_lots")
    op.drop_table("harvest_lot_sequences")
    op.drop_column("farms", "logo_url")
    op.drop_column("farms", "public_producer_name")
    op.drop_column("farms", "country")
    op.execute("DROP TYPE IF EXISTS passport_status")
