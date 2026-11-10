from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PassportStatus, pg_enum

if TYPE_CHECKING:
    from app.models.farm import Farm
    from app.models.harvest import HarvestEvent
    from app.models.parcel import Parcel
    from app.models.user import User


class HarvestLotSequence(Base):
    """Yearly counter for human-readable lot numbers (AT-YYYY-NNNNN)."""

    __tablename__ = "harvest_lot_sequences"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class HarvestLot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "harvest_lots"
    __table_args__ = (UniqueConstraint("lot_number", name="uq_harvest_lots_lot_number"),)

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    harvest_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("harvest_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lot_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    harvest_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="kg")
    crop: Mapped[str] = mapped_column(String(128), nullable=False, default="Lesnik")
    variety: Mapped[str | None] = mapped_column(String(128), nullable=True)
    passport_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    passport_status: Mapped[PassportStatus] = mapped_column(
        pg_enum(PassportStatus, "passport_status"),
        nullable=False,
        default=PassportStatus.PUBLISHED,
        index=True,
    )
    # Section visibility for the public passport (producer-controlled).
    visibility: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    allow_indexing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    passport_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    farm: Mapped[Farm] = relationship("Farm")
    parcel: Mapped[Parcel] = relationship("Parcel")
    harvest: Mapped[HarvestEvent] = relationship("HarvestEvent")
    snapshots: Mapped[list[PassportSnapshot]] = relationship(
        "PassportSnapshot",
        back_populates="harvest_lot",
        order_by="PassportSnapshot.version",
    )


class PassportSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable public declaration captured when a lot is finalized."""

    __tablename__ = "passport_snapshots"
    __table_args__ = (
        UniqueConstraint("harvest_lot_id", "version", name="uq_passport_snapshots_lot_version"),
    )

    harvest_lot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("harvest_lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    passport_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    harvest_lot: Mapped[HarvestLot] = relationship("HarvestLot", back_populates="snapshots")
