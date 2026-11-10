from __future__ import annotations

from datetime import date
from uuid import UUID

from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ActivitySemanticType,
    ActivityStatus,
    DiseaseSeverity,
    ObservationCategory,
    ObservationStatus,
    pg_enum,
)
from app.models.mixins import ScopedEntityMixin

_ACTIVITY_SEMANTIC_TYPE = pg_enum(ActivitySemanticType, "activity_semantic_type")
_OBSERVATION_CATEGORY = pg_enum(ObservationCategory, "observation_category")
_OBSERVATION_STATUS = pg_enum(ObservationStatus, "observation_status")
_DISEASE_SEVERITY = pg_enum(DiseaseSeverity, "disease_severity")


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
    semantic_type: Mapped[ActivitySemanticType] = mapped_column(
        _ACTIVITY_SEMANTIC_TYPE,
        default=ActivitySemanticType.OTHER,
        nullable=False,
        index=True,
    )
    observation_category: Mapped[ObservationCategory | None] = mapped_column(
        _OBSERVATION_CATEGORY,
        nullable=True,
        index=True,
    )
    observation_severity: Mapped[DiseaseSeverity | None] = mapped_column(
        _DISEASE_SEVERITY,
        nullable=True,
    )
    observation_status: Mapped[ObservationStatus | None] = mapped_column(
        _OBSERVATION_STATUS,
        nullable=True,
        index=True,
    )
    # Treatment → observation; follow-up may also reference prior observation.
    observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Treatment → planning item (nullable when treatment is ad-hoc).
    plan_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_plan_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Follow-up observation/treatment → prior observation or treatment.
    follow_up_of_id: Mapped[UUID | None] = mapped_column(
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
    schedule_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("task_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    activity_type: Mapped[ActivityType] = relationship("ActivityType", back_populates="activities")
    schedule: Mapped["TaskSchedule | None"] = relationship("TaskSchedule", back_populates="activities")
    costs: Mapped[list["Cost"]] = relationship(
        "Cost",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    soil_analyses: Mapped[list["SoilLabAnalysis"]] = relationship(
        "SoilLabAnalysis",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    related_observation: Mapped[Activity | None] = relationship(
        "Activity",
        foreign_keys=[observation_id],
        remote_side="Activity.id",
    )
    follow_up_of: Mapped[Activity | None] = relationship(
        "Activity",
        foreign_keys=[follow_up_of_id],
        remote_side="Activity.id",
    )
