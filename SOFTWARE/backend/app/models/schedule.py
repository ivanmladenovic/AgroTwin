from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrchardSeason(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Named date window for orchard work (irrigation, harvest, pruning, …)."""

    __tablename__ = "orchard_seasons"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="ck_orchard_seasons_range"),
    )

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    schedules: Mapped[list["TaskSchedule"]] = relationship("TaskSchedule", back_populates="season")


class TaskSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recurring planned work (e.g. irrigate Mon/Wed/Fri during a season)."""

    __tablename__ = "task_schedules"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="ck_task_schedules_range"),
    )

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    season_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orchard_seasons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    activity_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activity_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Monday=0 … Sunday=6 (Python date.weekday())
    weekdays: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    season: Mapped[OrchardSeason | None] = relationship("OrchardSeason", back_populates="schedules")
    activity_type: Mapped["ActivityType"] = relationship("ActivityType")
    activities: Mapped[list["Activity"]] = relationship("Activity", back_populates="schedule")
