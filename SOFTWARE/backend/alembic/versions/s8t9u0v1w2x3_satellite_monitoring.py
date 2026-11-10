"""satellite monitoring observations, zones, anomalies

Revision ID: s8t9u0v1w2x3
Revises: r7s8t9u0v1w2
Create Date: 2026-10-08 14:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "s8t9u0v1w2x3"
down_revision: Union[str, Sequence[str], None] = "r7s8t9u0v1w2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    satellite_processing_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "skipped",
        name="satellite_processing_status",
    )
    satellite_anomaly_kind = postgresql.ENUM(
        "below_parcel_mean",
        "sudden_decline",
        "persistent_low",
        name="satellite_anomaly_kind",
    )
    satellite_processing_status.create(op.get_bind(), checkfirst=True)
    satellite_anomaly_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "satellite_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("satellite", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=256), nullable=False),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("acquisition_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cloud_cover", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("requested_cloud_threshold", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("ndvi_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_stddev", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_mean", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_min", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi_max", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("image_reference", sa.String(length=512), nullable=True),
        sa.Column("visualization_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("index_formulas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_status", satellite_processing_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("anomaly_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "provider",
            "product_id",
            name="uq_satellite_observations_parcel_provider_product",
        ),
    )
    op.create_index("ix_satellite_observations_parcel_id", "satellite_observations", ["parcel_id"])
    op.create_index("ix_satellite_observations_provider", "satellite_observations", ["provider"])
    op.create_index(
        "ix_satellite_observations_acquisition_date",
        "satellite_observations",
        ["acquisition_date"],
    )
    op.create_index(
        "ix_satellite_observations_processing_status",
        "satellite_observations",
        ["processing_status"],
    )

    op.create_table(
        "satellite_zone_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_key", sa.String(length=64), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ndvi", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndre", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndwi", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("ndvi_deviation", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.ForeignKeyConstraint(["observation_id"], ["satellite_observations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id",
            "zone_key",
            name="uq_satellite_zone_metrics_observation_zone",
        ),
    )
    op.create_index(
        "ix_satellite_zone_metrics_observation_id",
        "satellite_zone_metrics",
        ["observation_id"],
    )

    op.create_table(
        "satellite_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_key", sa.String(length=64), nullable=True),
        sa.Column("kind", satellite_anomaly_kind, nullable=False),
        sa.Column("index_name", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["satellite_observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_satellite_anomalies_observation_id", "satellite_anomalies", ["observation_id"])
    op.create_index("ix_satellite_anomalies_parcel_id", "satellite_anomalies", ["parcel_id"])


def downgrade() -> None:
    op.drop_index("ix_satellite_anomalies_parcel_id", table_name="satellite_anomalies")
    op.drop_index("ix_satellite_anomalies_observation_id", table_name="satellite_anomalies")
    op.drop_table("satellite_anomalies")
    op.drop_index("ix_satellite_zone_metrics_observation_id", table_name="satellite_zone_metrics")
    op.drop_table("satellite_zone_metrics")
    op.drop_index("ix_satellite_observations_processing_status", table_name="satellite_observations")
    op.drop_index("ix_satellite_observations_acquisition_date", table_name="satellite_observations")
    op.drop_index("ix_satellite_observations_provider", table_name="satellite_observations")
    op.drop_index("ix_satellite_observations_parcel_id", table_name="satellite_observations")
    op.drop_table("satellite_observations")
    op.execute("DROP TYPE IF EXISTS satellite_anomaly_kind")
    op.execute("DROP TYPE IF EXISTS satellite_processing_status")
