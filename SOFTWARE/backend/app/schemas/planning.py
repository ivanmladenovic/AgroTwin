from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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
)
from app.schemas.common import IDSchema


class PlanningSeasonCreate(BaseModel):
    year: int = Field(ge=1990, le=2100)
    status: PlanningSeasonStatus = PlanningSeasonStatus.DRAFT
    copy_from_season_id: UUID | None = None
    copy_previous_plan: bool = False


class PlanningSeasonUpdate(BaseModel):
    status: PlanningSeasonStatus | None = None


class PlanningPlanCreate(BaseModel):
    type: PlanningPlanType
    status: PlanningPlanStatus = PlanningPlanStatus.DRAFT
    version: int = Field(default=1, ge=1)


class PlanningPlanItemCreate(BaseModel):
    scope_type: PlanningScopeType = PlanningScopeType.PARCEL
    scope_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    priority: int = Field(default=0, ge=0, le=100)
    priority_level: PlanningPriorityLevel = PlanningPriorityLevel.INFO
    priority_reason: str | None = None
    item_kind: PlanningItemKind = PlanningItemKind.MONITORING
    stream: PlanningStream = PlanningStream.PREVENTIVE
    reason: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    related_activity_id: UUID | None = None
    status: PlanningItemStatus = PlanningItemStatus.PLANNED
    source: PlanningItemSource = PlanningItemSource.USER
    expert_review_status: PlanningExpertReviewStatus = PlanningExpertReviewStatus.NOT_REQUIRED

    @model_validator(mode="after")
    def validate_dates_and_ai(self) -> "PlanningPlanItemCreate":
        if (
            self.planned_date_from is not None
            and self.planned_date_to is not None
            and self.planned_date_to < self.planned_date_from
        ):
            raise ValueError("Datum do ne može biti pre datuma od.")
        if self.source == PlanningItemSource.AI and self.status == PlanningItemStatus.APPROVED:
            raise ValueError("AI stavka ne sme automatski biti odobrena.")
        if self.source == PlanningItemSource.AI and self.expert_review_status == PlanningExpertReviewStatus.NOT_REQUIRED:
            self.expert_review_status = PlanningExpertReviewStatus.PENDING
        return self


class PlanningPlanItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    priority_level: PlanningPriorityLevel | None = None
    priority_reason: str | None = None
    status: PlanningItemStatus | None = None
    expert_review_status: PlanningExpertReviewStatus | None = None
    related_activity_id: UUID | None = None


class ProtectionPlanGenerateRequest(BaseModel):
    replace_generated: bool = True
    include_knowledge: bool = True


class NutritionPlanGenerateRequest(BaseModel):
    replace_generated: bool = True
    include_knowledge: bool = True


class IrrigationPlanGenerateRequest(BaseModel):
    replace_generated: bool = True
    include_knowledge: bool = True


class PlanningPlanItemRead(IDSchema):
    plan_id: UUID
    scope_type: PlanningScopeType
    scope_id: UUID
    title: str
    description: str | None
    planned_date_from: date | None
    planned_date_to: date | None
    priority: int
    priority_level: PlanningPriorityLevel = PlanningPriorityLevel.INFO
    priority_reason: str | None = None
    item_kind: PlanningItemKind = PlanningItemKind.MONITORING
    stream: PlanningStream = PlanningStream.PREVENTIVE
    reason: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    related_activity_id: UUID | None = None
    status: PlanningItemStatus
    source: PlanningItemSource
    expert_review_status: PlanningExpertReviewStatus
    source_season_id: UUID | None = None
    source_plan_id: UUID | None = None
    source_plan_item_id: UUID | None = None
    display_status: str = "proposal"
    display_status_label: str = "PREDLOG"
    requires_expert_review: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)
    expert_reviews: list["ExpertReviewRead"] = Field(default_factory=list)


class ExpertReviewSubmitRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ExpertReviewDecisionRequest(BaseModel):
    status: ExpertReviewStatus
    comment: str | None = Field(default=None, max_length=4000)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    reason: str | None = None
    priority_level: PlanningPriorityLevel | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> "ExpertReviewDecisionRequest":
        if self.status == ExpertReviewStatus.PENDING:
            raise ValueError("Odluka ne može ostati PENDING.")
        if self.status == ExpertReviewStatus.MODIFIED and not (
            self.title or self.description is not None or self.reason is not None or self.comment
        ):
            raise ValueError("Za MODIFY unesite izmenu (title/description/reason) ili komentar.")
        return self


class ExpertReviewRead(IDSchema):
    plan_item_id: UUID
    farm_id: UUID
    requested_by_id: UUID | None = None
    reviewer_id: UUID | None = None
    reviewer_name: str | None = None
    status: ExpertReviewStatus
    reviewed_at: datetime | None = None
    comment: str | None = None
    original_recommendation_snapshot: dict[str, Any] = Field(default_factory=dict)
    reviewed_recommendation_snapshot: dict[str, Any] | None = None


class PlanningPlanRead(IDSchema):
    planning_season_id: UUID
    type: PlanningPlanType
    status: PlanningPlanStatus
    version: int
    item_count: int = 0
    items: list[PlanningPlanItemRead] = Field(default_factory=list)


class PlanningSeasonRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID
    parcel_name: str | None = None
    year: int
    status: PlanningSeasonStatus
    copied_from_season_id: UUID | None = None
    created_by_id: UUID | None = None
    plans: list[PlanningPlanRead] = Field(default_factory=list)


class PlanningCopyRequest(BaseModel):
    source_season_id: UUID


class PlanningActivitySnippet(BaseModel):
    id: UUID
    title: str
    performed_on: date
    activity_type: str | None = None
    status: str
    semantic_type: str | None = None
    scope_type: str | None = None
    observation_category: str | None = None
    observation_status: str | None = None
    observation_id: UUID | None = None
    follow_up_of_id: UUID | None = None
    plan_item_id: UUID | None = None


class PlanningSoilSnippet(BaseModel):
    id: UUID
    sampled_on: date
    original_filename: str
    tree_id: UUID
    verification_status: str | None = None
    laboratory_name: str | None = None
    result_count: int = 0
    source_kind: str = "laboratory"


class PlanningPreviousPlanSnippet(BaseModel):
    season_id: UUID
    year: int
    plan_id: UUID
    plan_type: PlanningPlanType
    status: PlanningPlanStatus
    item_count: int


class PlanningPriorityItem(BaseModel):
    plan_item_id: UUID
    plan_id: UUID
    plan_type: PlanningPlanType
    title: str
    display_status: str
    display_status_label: str
    priority_level: PlanningPriorityLevel
    planned_date_from: date | None = None
    scope_type: PlanningScopeType
    scope_id: UUID
    expert_review_status: PlanningExpertReviewStatus
    reason: str | None = None


class PlanningDomainCard(BaseModel):
    plan_type: PlanningPlanType
    plan_id: UUID | None = None
    status: str
    next_actions: list[str] = Field(default_factory=list)
    active_observations: int = 0
    expert_review_pending: int = 0
    expert_review_count: int = 0
    soil_analysis: str | None = None
    system_status: str | None = None
    item_count: int = 0


class PlanningDashboard(BaseModel):
    parcel_id: UUID
    parcel_name: str
    year: int
    season_id: UUID | None = None
    season_status: PlanningSeasonStatus | None = None
    previous_season: PlanningSeasonRead | None = None
    priorities: list[PlanningPriorityItem] = Field(default_factory=list)
    protection: PlanningDomainCard
    nutrition: PlanningDomainCard
    irrigation: PlanningDomainCard


class PlanningParcelSummary(BaseModel):
    parcel_id: UUID
    parcel_name: str
    farm_id: UUID
    area_hectares: float | None = None
    default_variety: str | None = None
    varieties: list[str] = Field(default_factory=list)
    default_planting_year: int | None = None
    well_location: str | None = None
    irrigation_hint: str | None = None
    has_irrigation: bool = False
    irrigation_type: str | None = None
    organic_status: str | None = None
    organic_status_note: str = ""
    latest_soil_analysis: PlanningSoilSnippet | None = None
    recent_activities: list[PlanningActivitySnippet] = Field(default_factory=list)
    seasons: list[PlanningSeasonRead] = Field(default_factory=list)
    previous_plans: list[PlanningPreviousPlanSnippet] = Field(default_factory=list)
