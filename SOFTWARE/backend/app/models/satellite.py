from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SatelliteAnomalyKind, SatelliteProcessingStatus, pg_enum

if TYPE_CHECKING:
    from app.models.parcel import Parcel


class SatelliteObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "satellite_observations"
    __table_args__ = (
        UniqueConstraint(
            "parcel_id",
            "provider",
            "product_id",
            name="uq_satellite_observations_parcel_provider_product",
        ),
    )

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    satellite: Mapped[str] = mapped_column(String(64), nullable=False, default="Sentinel-2")
    product_id: Mapped[str] = mapped_column(String(256), nullable=False)
    acquisition_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    acquisition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cloud_cover: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    requested_cloud_threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    ndvi_mean: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndvi_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndvi_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndvi_stddev: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    ndre_mean: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndre_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndre_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    ndwi_mean: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndwi_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndwi_max: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    image_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    visualization_refs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    index_formulas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    processing_status: Mapped[SatelliteProcessingStatus] = mapped_column(
        pg_enum(SatelliteProcessingStatus, "satellite_processing_status"),
        nullable=False,
        default=SatelliteProcessingStatus.PENDING,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    parcel: Mapped["Parcel"] = relationship("Parcel")
    zones: Mapped[list[SatelliteZoneMetric]] = relationship(
        "SatelliteZoneMetric",
        back_populates="observation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    anomalies: Mapped[list[SatelliteAnomaly]] = relationship(
        "SatelliteAnomaly",
        back_populates="observation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SatelliteZoneMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "satellite_zone_metrics"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "zone_key",
            name="uq_satellite_zone_metrics_observation_zone",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("satellite_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_key: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ndvi: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndre: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndwi: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    ndvi_deviation: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    observation: Mapped[SatelliteObservation] = relationship(
        "SatelliteObservation",
        back_populates="zones",
    )


class SatelliteAnomaly(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "satellite_anomalies"

    observation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("satellite_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[SatelliteAnomalyKind] = mapped_column(
        pg_enum(SatelliteAnomalyKind, "satellite_anomaly_kind"),
        nullable=False,
    )
    index_name: Mapped[str] = mapped_column(String(16), nullable=False, default="ndvi")
    severity: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    observation: Mapped[SatelliteObservation] = relationship(
        "SatelliteObservation",
        back_populates="anomalies",
    )
