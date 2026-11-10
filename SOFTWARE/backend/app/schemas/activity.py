from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    ActivitySemanticType,
    ActivityStatus,
    DiseaseSeverity,
    ObservationCategory,
    ObservationStatus,
    ScopeType,
)
from app.schemas.catalog import CatalogItemRead
from app.schemas.common import IDSchema
from app.schemas.cost import CostItemRead
from app.schemas.disease import PhotoRead
from app.schemas.soil_lab import SoilLabAnalysisRead


class ActivityLineItem(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=32)
    volume: Decimal | None = Field(default=None, ge=0)
    volume_unit: str | None = Field(default=None, max_length=32)
    amount: Decimal | None = Field(default=None, ge=0)


class ActivityCreate(BaseModel):
    activity_type_id: UUID
    performed_on: date
    scope_type: ScopeType
    parcel_id: UUID
    row_id: UUID | None = None
    row_ids: list[UUID] = Field(default_factory=list)
    tree_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, max_length=32)
    line_items: list[ActivityLineItem] = Field(default_factory=list)
    cost_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    status: ActivityStatus | None = None
    semantic_type: ActivitySemanticType | None = None
    observation_category: ObservationCategory | None = None
    observation_severity: DiseaseSeverity | None = None
    observation_status: ObservationStatus | None = None
    observation_id: UUID | None = None
    plan_item_id: UUID | None = None
    follow_up_of_id: UUID | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "ActivityCreate":
        if self.scope_type == ScopeType.FARM:
            raise ValueError("Aktivnosti na nivou gazdinstva se u ovoj fazi ne koriste.")
        if self.scope_type == ScopeType.PARCEL and (self.row_id is not None or self.tree_id is not None or self.row_ids):
            raise ValueError("Aktivnosti parcele ne smeju da uključuju red ili stablo.")
        if self.scope_type == ScopeType.ROW:
            row_ids = list(dict.fromkeys(self.row_ids or ([self.row_id] if self.row_id else [])))
            if not row_ids or self.tree_id is not None:
                raise ValueError("Aktivnosti reda zahtevaju bar jedan red i ne smeju da uključuju stablo.")
            self.row_ids = row_ids
            self.row_id = row_ids[0]
        if self.scope_type == ScopeType.TREE and (self.row_id is None or self.tree_id is None):
            raise ValueError("Aktivnosti stabla zahtevaju i red i stablo.")
        return self

    @model_validator(mode="after")
    def validate_observation_fields(self) -> "ActivityCreate":
        semantic = self.semantic_type
        is_observation_like = semantic in {
            ActivitySemanticType.OBSERVATION,
            ActivitySemanticType.PROBLEM,
            ActivitySemanticType.MONITORING,
        }
        if is_observation_like:
            if self.observation_status is None:
                self.observation_status = ObservationStatus.NEW
            if self.observation_category is None:
                self.observation_category = ObservationCategory.UNKNOWN
        if self.observation_status == ObservationStatus.CONFIRMED and semantic is None:
            # CONFIRMED is user-only; presence is fine on create from UI, blocked for AI elsewhere.
            pass
        return self


class ActivityUpdate(BaseModel):
    status: ActivityStatus | None = None
    performed_on: date | None = None
    notes: str | None = None
    description: str | None = None
    semantic_type: ActivitySemanticType | None = None
    observation_category: ObservationCategory | None = None
    observation_severity: DiseaseSeverity | None = None
    observation_status: ObservationStatus | None = None
    observation_id: UUID | None = None
    plan_item_id: UUID | None = None
    follow_up_of_id: UUID | None = None


class ActivityHarvestSnippet(BaseModel):
    id: UUID
    parcel_id: UUID | None = None
    harvested_on: date
    location_label: str
    gross_quantity: Decimal | None = None
    loss_quantity: Decimal = Decimal("0")
    net_quantity: Decimal | None = None
    unit: str
    quality_category: str | None = None
    notes: str | None = None


class ActivityPlanItemSnippet(BaseModel):
    id: UUID
    plan_id: UUID
    plan_type: str
    parcel_id: UUID | None = None
    year: int | None = None
    title: str
    planned_date_from: date | None = None
    planned_date_to: date | None = None
    status: str
    description: str | None = None
    products: list[dict] = Field(default_factory=list)


class ActivityDiseaseSnippet(BaseModel):
    id: UUID
    parcel_id: UUID | None = None
    title: str
    category: str
    severity: str
    status: str
    detected_on: date
    location_label: str
    notes: str | None = None


class ActivitySubsidySnippet(BaseModel):
    id: UUID
    parcel_id: UUID | None = None
    title: str
    total_cost: Decimal
    subsidy_amount: Decimal
    subsidy_percent: Decimal | None = None
    currency: str
    received_on: date
    notes: str | None = None


class ActivityRead(IDSchema):
    activity_type: CatalogItemRead
    title: str
    description: str | None
    performed_on: date
    status: ActivityStatus
    quantity: Decimal | None
    unit: str | None
    line_items: list[ActivityLineItem] = Field(default_factory=list)
    notes: str | None
    scope_type: ScopeType
    farm_id: UUID
    parcel_id: UUID | None
    row_id: UUID | None
    row_ids: list[UUID] = Field(default_factory=list)
    row_numbers: list[int] = Field(default_factory=list)
    tree_id: UUID | None
    parcel_name: str | None = None
    row_number: int | None = None
    tree_public_id: str | None = None
    costs: list[CostItemRead] = Field(default_factory=list)
    soil_analyses: list[SoilLabAnalysisRead] = Field(default_factory=list)
    photos: list[PhotoRead] = Field(default_factory=list)
    harvest: ActivityHarvestSnippet | None = None
    plan_item: ActivityPlanItemSnippet | None = None
    disease_case: ActivityDiseaseSnippet | None = None
    subsidy: ActivitySubsidySnippet | None = None
    total_cost: Decimal
    currency: str = "EUR"
    semantic_type: ActivitySemanticType = ActivitySemanticType.OTHER
    observation_category: ObservationCategory | None = None
    observation_severity: DiseaseSeverity | None = None
    observation_status: ObservationStatus | None = None
    observation_id: UUID | None = None
    plan_item_id: UUID | None = None
    follow_up_of_id: UUID | None = None
