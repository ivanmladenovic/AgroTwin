from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OrganicScope, PlantingBatchScope, ProductionMethod
from app.schemas.common import IDSchema


class PlantingBatchCreate(BaseModel):
    year: int = Field(ge=1900, le=2100)
    quantity: int = Field(ge=1)
    scope_type: PlantingBatchScope = PlantingBatchScope.PARCEL
    row_id: UUID | None = None
    row_number_from: int | None = Field(default=None, ge=1)
    row_number_to: int | None = Field(default=None, ge=1)
    planted_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    apply_to_layout: bool = True

    @model_validator(mode="after")
    def validate_scope(self) -> "PlantingBatchCreate":
        if self.scope_type == PlantingBatchScope.ROW:
            if self.row_id is None and (self.row_number_from is None or self.row_number_to is None):
                raise ValueError("Za scope reda unesite red ili opseg redova.")
            if self.row_number_from is not None and self.row_number_to is not None:
                if self.row_number_to < self.row_number_from:
                    raise ValueError("Kraj opsega redova ne može biti pre početka.")
        return self


class PlantingBatchRead(IDSchema):
    parcel_id: UUID
    year: int
    quantity: int
    scope_type: PlantingBatchScope
    row_id: UUID | None = None
    row_number_from: int | None = None
    row_number_to: int | None = None
    planted_on: date | None = None
    notes: str | None = None
    created_by_id: UUID | None = None


class PlantingYearBucket(BaseModel):
    year: int = Field(ge=1900, le=2100)
    tree_count: int = Field(ge=0)


class PlantingDistributionUpdate(BaseModel):
    """Replace planting-year assignment across active trees on the parcel."""

    years: list[PlantingYearBucket] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_years(self) -> "PlantingDistributionUpdate":
        seen: set[int] = set()
        cleaned: list[PlantingYearBucket] = []
        for item in self.years:
            if item.tree_count <= 0:
                continue
            if item.year in seen:
                raise ValueError(f"Godina {item.year} je uneta više puta.")
            seen.add(item.year)
            cleaned.append(item)
        self.years = cleaned
        return self


class PlantingSummaryRead(BaseModel):
    parcel_id: UUID
    total_active_trees: int
    default_planting_year: int | None
    planting_period_label: str
    years: list[PlantingYearBucket]
    unknown_tree_count: int
    precision_note: str | None = None
    batches: list[PlantingBatchRead] = Field(default_factory=list)
    production_method: ProductionMethod
    organic_scope: OrganicScope


class OrganicRowsUpdate(BaseModel):
    row_ids: list[UUID] = Field(default_factory=list)
