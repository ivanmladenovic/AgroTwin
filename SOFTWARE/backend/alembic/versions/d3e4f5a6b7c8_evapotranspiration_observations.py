"""clms actual evapotranspiration observations

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-20 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evapotranspiration_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=16), nullable=False),
        sa.Column("dataset_version", sa.String(length=16), nullable=False),
        sa.Column("collection_id", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("eta_value", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("evaporation", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("transpiration", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("spatial_resolution", sa.String(length=16), nullable=False),
        sa.Column("geometry_source", sa.String(length=32), nullable=False),
        sa.Column("statistic", sa.String(length=32), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "dataset",
            "dataset_version",
            "period_start",
            "period_end",
            name="uq_eta_obs_parcel_dataset_period",
        ),
    )
    op.create_index(
        op.f("ix_evapotranspiration_observations_parcel_id"),
        "evapotranspiration_observations",
        ["parcel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evapotranspiration_observations_period_end"),
        "evapotranspiration_observations",
        ["period_end"],
        unique=False,
    )

    op.create_table(
        "evapotranspiration_query_caches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_kind", sa.String(length=32), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("coord_hash", sa.String(length=32), nullable=False),
        sa.Column("catalog_version", sa.String(length=32), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "query_kind",
            "period_days",
            "coord_hash",
            "catalog_version",
            name="uq_eta_query_caches_lookup",
        ),
    )
    op.create_index(
        op.f("ix_evapotranspiration_query_caches_parcel_id"),
        "evapotranspiration_query_caches",
        ["parcel_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_evapotranspiration_query_caches_parcel_id"), table_name="evapotranspiration_query_caches")
    op.drop_table("evapotranspiration_query_caches")
    op.drop_index(op.f("ix_evapotranspiration_observations_period_end"), table_name="evapotranspiration_observations")
    op.drop_index(op.f("ix_evapotranspiration_observations_parcel_id"), table_name="evapotranspiration_observations")
    op.drop_table("evapotranspiration_observations")
