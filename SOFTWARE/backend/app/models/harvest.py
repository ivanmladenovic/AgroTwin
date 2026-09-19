from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Computed, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HarvestQualityCategory, pg_enum
from app.models.mixins import ScopedEntityMixin


class HarvestEvent(UUIDPrimaryKeyMixin, TimestampMixin, ScopedEntityMixin, Base):
    """Recorded harvest quantity and quality. Not a sale and not a journal activity."""

    __tablename__ = "harvest_events"
    __table_args__ = (
        ScopedEntityMixin.scope_check_constraint("harvest_events"),
        CheckConstraint("gross_quantity > 0", name="ck_harvest_events_gross_positive"),
        CheckConstraint("loss_quantity >= 0", name="ck_harvest_events_loss_nonnegative"),
        CheckConstraint("loss_quantity <= gross_quantity", name="ck_harvest_events_loss_lte_gross"),
        CheckConstraint(
            "moisture_percent IS NULL OR (moisture_percent >= 0 AND moisture_percent <= 100)",
            name="ck_harvest_events_moisture",
        ),
        CheckConstraint(
            "damaged_percent IS NULL OR (damaged_percent >= 0 AND damaged_percent <= 100)",
            name="ck_harvest_events_damaged",
        ),
        CheckConstraint(
            "empty_nuts_percent IS NULL OR (empty_nuts_percent >= 0 AND empty_nuts_percent <= 100)",
            name="ck_harvest_events_empty_nuts",
        ),
        CheckConstraint(
            "foreign_material_percent IS NULL OR (foreign_material_percent >= 0 AND foreign_material_percent <= 100)",
            name="ck_harvest_events_foreign_material",
        ),
    )

    harvested_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    gross_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    loss_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=Decimal("0"))
    net_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        Computed("gross_quantity - loss_quantity", persisted=True),
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="kg")
    moisture_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    quality_category: Mapped[HarvestQualityCategory | None] = mapped_column(
        pg_enum(HarvestQualityCategory, "harvest_quality_category"),
        nullable=True,
        index=True,
    )
    damaged_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    empty_nuts_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    foreign_material_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    size_or_caliber: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by: Mapped["User | None"] = relationship("User")
