"""weather forecast cache for parcels

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-09-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_forecast_caches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parcel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_modified", sa.String(length=128), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized_response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parcel_id", name="uq_weather_forecast_caches_parcel_id"),
    )
    op.create_index(op.f("ix_weather_forecast_caches_parcel_id"), "weather_forecast_caches", ["parcel_id"], unique=False)
    op.create_index(
        op.f("ix_weather_forecast_caches_forecast_date"),
        "weather_forecast_caches",
        ["forecast_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_weather_forecast_caches_forecast_date"), table_name="weather_forecast_caches")
    op.drop_index(op.f("ix_weather_forecast_caches_parcel_id"), table_name="weather_forecast_caches")
    op.drop_table("weather_forecast_caches")
