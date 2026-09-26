"""sentinel-2 observations and optional parcel boundary

Revision ID: a9b0c1d2e3f4
Revises: c0d1e2f3a4b5
Create Date: 2026-09-20 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parcels", sa.Column("altitude", sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column("parcels", sa.Column("boundary", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table(
        "satellite_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("satellite", sa.String(length=32), nullable=False),
        sa.Column("product", sa.String(length=32), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("acquisition_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_cloud_threshold", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("cloud_coverage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("valid_pixel_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("valid_pixel_count", sa.Integer(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("geometry_source", sa.String(length=32), nullable=False),
        sa.Column("index_calculation_version", sa.String(length=16), nullable=False),
        sa.Column("ndvi_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_resolution_m", sa.Integer(), nullable=False),
        sa.Column("ndre_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_resolution_m", sa.Integer(), nullable=False),
        sa.Column("gndvi_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("gndvi_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("gndvi_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("gndvi_resolution_m", sa.Integer(), nullable=False),
        sa.Column("ndwi_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_resolution_m", sa.Integer(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "observation_date",
            "provider",
            "product",
            "index_calculation_version",
            name="uq_satellite_observations_parcel_date",
        ),
    )
    op.create_index(
        op.f("ix_satellite_observations_parcel_id"),
        "satellite_observations",
        ["parcel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_satellite_observations_observation_date"),
        "satellite_observations",
        ["observation_date"],
        unique=False,
    )

    op.create_table(
        "satellite_query_caches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_kind", sa.String(length=32), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("geometry_hash", sa.String(length=64), nullable=False),
        sa.Column("index_calculation_version", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("observation_date", sa.Date(), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "query_kind",
            "period_days",
            "layer",
            "geometry_hash",
            "index_calculation_version",
            name="uq_satellite_query_caches_lookup",
        ),
    )
    op.create_index(
        op.f("ix_satellite_query_caches_parcel_id"),
        "satellite_query_caches",
        ["parcel_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_satellite_query_caches_parcel_id"), table_name="satellite_query_caches")
    op.drop_table("satellite_query_caches")
    op.drop_index(op.f("ix_satellite_observations_observation_date"), table_name="satellite_observations")
    op.drop_index(op.f("ix_satellite_observations_parcel_id"), table_name="satellite_observations")
    op.drop_table("satellite_observations")
    op.drop_column("parcels", "boundary")
    op.drop_column("parcels", "altitude")
