from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.mixins import ScopedEntityMixin


class CostCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cost_categories"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    costs: Mapped[list[Cost]] = relationship("Cost", back_populates="cost_category")


class Cost(UUIDPrimaryKeyMixin, TimestampMixin, ScopedEntityMixin, Base):
    __tablename__ = "costs"
    __table_args__ = (ScopedEntityMixin.scope_check_constraint("costs"),)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    incurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("cost_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    activity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    activity: Mapped["Activity"] = relationship("Activity", back_populates="costs")
    cost_category: Mapped[CostCategory] = relationship("CostCategory", back_populates="costs")
