from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SoilProfileSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cached SoilGrids modeled soil profile for one parcel."""

    __tablename__ = "soil_profile_snapshots"
    __table_args__ = (UniqueConstraint("parcel_id", name="uq_soil_profile_snapshots_parcel_id"),)

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="SoilGrids")
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False, default="2.0")
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_properties: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    parcel: Mapped["Parcel"] = relationship("Parcel")
