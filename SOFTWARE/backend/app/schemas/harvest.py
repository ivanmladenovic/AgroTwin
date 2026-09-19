from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import HarvestQualityCategory, ScopeType
from app.schemas.common import IDSchema
from app.schemas.disease import PhotoRead
from app.schemas.report import OptionalAmount, YearChange


class HarvestEventCreate(BaseModel):
    harvested_on: date
    scope_type: ScopeType
    row_id: UUID | None = None
    tree_id: UUID | None = None
    gross_quantity: Decimal = Field(gt=0)
    loss_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    unit: str = Field(default="kg", min_length=1, max_length=32)
    moisture_percent: Decimal | None = Field(default=None, ge=0, le=100)
    quality_category: HarvestQualityCategory | None = None
    damaged_percent: Decimal | None = Field(default=None, ge=0, le=100)
    empty_nuts_percent: Decimal | None = Field(default=None, ge=0, le=100)
    foreign_material_percent: Decimal | None = Field(default=None, ge=0, le=100)
    size_or_caliber: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    activity_id: UUID | None = None

    @model_validator(mode="after")
    def validate_quantities_and_scope(self) -> "HarvestEventCreate":
        if self.loss_quantity > self.gross_quantity:
            raise ValueError("Gubitak ne može biti veći od bruto količine.")
        if self.scope_type == ScopeType.FARM:
            raise ValueError("Berba na nivou gazdinstva se u ovoj fazi ne koristi.")
        if self.scope_type == ScopeType.PARCEL and (self.row_id is not None or self.tree_id is not None):
            raise ValueError("Berba parcele ne sme da uključuje red ili stablo.")
        if self.scope_type == ScopeType.ROW and (self.row_id is None or self.tree_id is not None):
            raise ValueError("Berba reda zahteva red i ne sme da uključuje stablo.")
        if self.scope_type == ScopeType.TREE and self.tree_id is None:
            raise ValueError("Berba stabla zahteva stablo.")
        return self


class HarvestEventUpdate(BaseModel):
    harvested_on: date | None = None
    scope_type: ScopeType | None = None
    row_id: UUID | None = None
    tree_id: UUID | None = None
    gross_quantity: Decimal | None = Field(default=None, gt=0)
    loss_quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    moisture_percent: Decimal | None = Field(default=None, ge=0, le=100)
    quality_category: HarvestQualityCategory | None = None
    damaged_percent: Decimal | None = Field(default=None, ge=0, le=100)
    empty_nuts_percent: Decimal | None = Field(default=None, ge=0, le=100)
    foreign_material_percent: Decimal | None = Field(default=None, ge=0, le=100)
    size_or_caliber: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    activity_id: UUID | None = None
    clear_quality_category: bool = False
    clear_activity_id: bool = False


class HarvestEventRead(IDSchema):
    harvested_on: date
    scope_type: ScopeType
    farm_id: UUID
    parcel_id: UUID | None
    row_id: UUID | None
    tree_id: UUID | None
    parcel_name: str | None = None
    row_number: int | None = None
    tree_public_id: str | None = None
    tree_status: str | None = None
    location_label: str
    gross_quantity: Decimal
    loss_quantity: Decimal
    net_quantity: Decimal
    unit: str
    gross_kg: Decimal | None = None
    loss_kg: Decimal | None = None
    net_kg: Decimal | None = None
    moisture_percent: Decimal | None = None
    quality_category: HarvestQualityCategory | None = None
    damaged_percent: Decimal | None = None
    empty_nuts_percent: Decimal | None = None
    foreign_material_percent: Decimal | None = None
    size_or_caliber: str | None = None
    notes: str | None = None
    activity_id: UUID | None = None
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    photos: list[PhotoRead] = Field(default_factory=list)


class HarvestTimelinePoint(BaseModel):
    harvested_on: date
    event_count: int
    gross_kg: Decimal
    loss_kg: Decimal
    net_kg: Decimal
    cumulative_net_kg: Decimal


class HarvestRowSummary(BaseModel):
    row_id: UUID
    row_number: int
    harvest_event_count: int
    net_kg: Decimal
    active_trees: int
    yield_per_tree: OptionalAmount


class HarvestTreeSummary(BaseModel):
    tree_id: UUID
    public_id: str
    row_id: UUID
    row_number: int
    tree_status: str
    health_status: str
    net_kg: Decimal
    harvest_event_count: int


class QualityAverage(BaseModel):
    available: bool
    value: Decimal | None = None
    method: Literal["weighted"] | None = None
    sample_count: int = 0


class QualityCategoryShare(BaseModel):
    category: HarvestQualityCategory
    net_kg: Decimal
    event_count: int


class HarvestQualitySummary(BaseModel):
    recorded: bool
    moisture: QualityAverage
    damaged: QualityAverage
    empty_nuts: QualityAverage
    foreign_material: QualityAverage
    categories: list[QualityCategoryShare] = Field(default_factory=list)


class ProductionComparison(BaseModel):
    available: bool
    previous_year: int
    previous_net_yield: OptionalAmount
    previous_yield_per_hectare: OptionalAmount
    previous_harvest_event_count: int | None = None
    net_yield_change: YearChange
    yield_per_hectare_change: YearChange
    harvest_event_count_change: YearChange
    message: str | None = None


class ParcelProductionRead(BaseModel):
    parcel_id: UUID
    parcel_name: str
    year: int
    unit: str = "kg"
    area_hectares: Decimal | None = None
    active_trees: int
    available_years: list[int]
    recorded: bool
    parcel_total_recorded: bool
    measurement_note: str
    total_gross_quantity: OptionalAmount
    total_loss_quantity: OptionalAmount
    total_net_yield: OptionalAmount
    harvest_event_count: int | None = None
    all_event_count: int
    first_harvest_date: date | None = None
    last_harvest_date: date | None = None
    yield_per_hectare: OptionalAmount
    yield_per_tree: OptionalAmount
    yield_per_tree_denominator: str | None = None
    events: list[HarvestEventRead] = Field(default_factory=list)
    timeline: list[HarvestTimelinePoint] = Field(default_factory=list)
    row_summary: list[HarvestRowSummary] = Field(default_factory=list)
    tree_summary: list[HarvestTreeSummary] = Field(default_factory=list)
    quality_summary: HarvestQualitySummary
    comparison: ProductionComparison
    photos: list[PhotoRead] = Field(default_factory=list)
