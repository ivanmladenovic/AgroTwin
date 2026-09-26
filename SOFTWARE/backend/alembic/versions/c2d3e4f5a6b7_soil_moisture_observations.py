"""clms soil moisture observations

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-20 13:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "soil_moisture_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("dataset", sa.String(length=16), nullable=False),
        sa.Column("dataset_version", sa.String(length=16), nullable=False),
        sa.Column("collection_id", sa.String(length=64), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("ssm", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("ssm_noise", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("swi_040", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("swi_060", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("swi_100", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("spatial_resolution", sa.String(length=16), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parcel_id",
            "dataset",
            "dataset_version",
            "observation_date",
            name="uq_soil_moisture_obs_parcel_dataset_date",
        ),
    )
    op.create_index(
        op.f("ix_soil_moisture_observations_parcel_id"),
        "soil_moisture_observations",
        ["parcel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_soil_moisture_observations_observation_date"),
        "soil_moisture_observations",
        ["observation_date"],
        unique=False,
    )

    op.create_table(
        "soil_moisture_query_caches",
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
            name="uq_soil_moisture_query_caches_lookup",
        ),
    )
    op.create_index(
        op.f("ix_soil_moisture_query_caches_parcel_id"),
        "soil_moisture_query_caches",
        ["parcel_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_soil_moisture_query_caches_parcel_id"), table_name="soil_moisture_query_caches")
    op.drop_table("soil_moisture_query_caches")
    op.drop_index(op.f("ix_soil_moisture_observations_observation_date"), table_name="soil_moisture_observations")
    op.drop_index(op.f("ix_soil_moisture_observations_parcel_id"), table_name="soil_moisture_observations")
    op.drop_table("soil_moisture_observations")
