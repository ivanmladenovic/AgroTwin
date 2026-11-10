from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ExpertReviewStatus,
    PlanningExpertReviewStatus,
    PlanningItemKind,
    PlanningItemSource,
    PlanningItemStatus,
    PlanningPlanStatus,
    PlanningPlanType,
    PlanningPriorityLevel,
    PlanningScopeType,
    PlanningSeasonStatus,
    PlanningStream,
    pg_enum,
)

_PLANNING_ITEM_KIND = pg_enum(PlanningItemKind, "planning_item_kind")
_PLANNING_STREAM = pg_enum(PlanningStream, "planning_stream")
_PLANNING_PRIORITY_LEVEL = pg_enum(PlanningPriorityLevel, "planning_priority_level")
_EXPERT_REVIEW_STATUS = pg_enum(ExpertReviewStatus, "expert_review_status")


class PlanningSeason(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Parcel-centric production/planning year (distinct from OrchardSeason date windows)."""

    __tablename__ = "planning_seasons"
    __table_args__ = (
        UniqueConstraint("parcel_id", "year", name="uq_planning_seasons_parcel_year"),
    )

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
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[PlanningSeasonStatus] = mapped_column(
        pg_enum(PlanningSeasonStatus, "planning_season_status"),
        default=PlanningSeasonStatus.DRAFT,
        nullable=False,
    )
    copied_from_season_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_seasons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    plans: Mapped[list[PlanningPlan]] = relationship(
        "PlanningPlan",
        back_populates="season",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PlanningPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_plans"
    __table_args__ = (
        UniqueConstraint("planning_season_id", "type", "version", name="uq_planning_plans_season_type_version"),
    )

    planning_season_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[PlanningPlanType] = mapped_column(
        pg_enum(PlanningPlanType, "planning_plan_type"),
        nullable=False,
        index=True,
    )
    status: Mapped[PlanningPlanStatus] = mapped_column(
        pg_enum(PlanningPlanStatus, "planning_plan_status"),
        default=PlanningPlanStatus.DRAFT,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    season: Mapped[PlanningSeason] = relationship("PlanningSeason", back_populates="plans")
    items: Mapped[list[PlanningPlanItem]] = relationship(
        "PlanningPlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="PlanningPlanItem.plan_id",
    )


class PlanningPlanItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planning_plan_items"

    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_type: Mapped[PlanningScopeType] = mapped_column(
        pg_enum(PlanningScopeType, "planning_scope_type"),
        nullable=False,
        index=True,
    )
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_level: Mapped[PlanningPriorityLevel] = mapped_column(
        _PLANNING_PRIORITY_LEVEL,
        default=PlanningPriorityLevel.INFO,
        nullable=False,
    )
    priority_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_kind: Mapped[PlanningItemKind] = mapped_column(
        _PLANNING_ITEM_KIND,
        default=PlanningItemKind.MONITORING,
        nullable=False,
        index=True,
    )
    stream: Mapped[PlanningStream] = mapped_column(
        _PLANNING_STREAM,
        default=PlanningStream.PREVENTIVE,
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_data: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_activity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[PlanningItemStatus] = mapped_column(
        pg_enum(PlanningItemStatus, "planning_item_status"),
        default=PlanningItemStatus.PLANNED,
        nullable=False,
    )
    source: Mapped[PlanningItemSource] = mapped_column(
        pg_enum(PlanningItemSource, "planning_item_source"),
        default=PlanningItemSource.USER,
        nullable=False,
    )
    expert_review_status: Mapped[PlanningExpertReviewStatus] = mapped_column(
        pg_enum(PlanningExpertReviewStatus, "planning_expert_review_status"),
        default=PlanningExpertReviewStatus.NOT_REQUIRED,
        nullable=False,
    )
    source_season_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_seasons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_plan_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_plan_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_plan_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    plan: Mapped[PlanningPlan] = relationship(
        "PlanningPlan",
        back_populates="items",
        foreign_keys=[plan_id],
    )
    expert_reviews: Mapped[list["ExpertReview"]] = relationship(
        "ExpertReview",
        back_populates="plan_item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExpertReview.created_at",
    )


class ExpertReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only audit trail for expert review of a planning item recommendation."""

    __tablename__ = "expert_reviews"

    plan_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("planning_plan_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ExpertReviewStatus] = mapped_column(
        _EXPERT_REVIEW_STATUS,
        default=ExpertReviewStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_recommendation_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reviewed_recommendation_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    plan_item: Mapped[PlanningPlanItem] = relationship(
        "PlanningPlanItem",
        back_populates="expert_reviews",
    )
