from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PlantingBatchScope, pg_enum


class PlantingBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Declared planting period for (part of) a parcel.

    Complements Tree.planting_year / Row.planting_year — does not replace journal
    Activity history. Used for multi-year planting UX and planning context.
    """

    __tablename__ = "planting_batches"

    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[PlantingBatchScope] = mapped_column(
        pg_enum(PlantingBatchScope, "planting_batch_scope"),
        default=PlantingBatchScope.PARCEL,
        nullable=False,
    )
    row_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orchard_rows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    row_number_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_number_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    parcel: Mapped[Parcel] = relationship("Parcel", back_populates="planting_batches")
