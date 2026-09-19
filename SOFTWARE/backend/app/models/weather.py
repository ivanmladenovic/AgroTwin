from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeatherForecastCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Latest daily forecast cache for a parcel. One row per parcel."""

    __tablename__ = "weather_forecast_caches"
    __table_args__ = (UniqueConstraint("parcel_id", name="uq_weather_forecast_caches_parcel_id"),)

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="yr")
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    normalized_response: Mapped[dict] = mapped_column(JSONB, nullable=False)

    parcel: Mapped["Parcel"] = relationship("Parcel")
