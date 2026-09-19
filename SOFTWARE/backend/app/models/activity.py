from __future__ import annotations

from datetime import date
from uuid import UUID

from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ActivityStatus, pg_enum
from app.models.mixins import ScopedEntityMixin


class ActivityType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activity_types"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    activities: Mapped[list[Activity]] = relationship("Activity", back_populates="activity_type")


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, ScopedEntityMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (ScopedEntityMixin.scope_check_constraint("activities"),)

    activity_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activity_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    performed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[ActivityStatus] = mapped_column(
        pg_enum(ActivityStatus, "activity_status"),
        default=ActivityStatus.COMPLETED,
        nullable=False,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line_items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    extra_row_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    activity_type: Mapped[ActivityType] = relationship("ActivityType", back_populates="activities")
    costs: Mapped[list["Cost"]] = relationship(
        "Cost",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
