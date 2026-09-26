from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ScopeType
from app.schemas.catalog import CatalogItemRead
from app.schemas.common import IDSchema


class QuantityLineRead(BaseModel):
    name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    volume: Decimal | None = None
    volume_unit: str | None = None
    amount: Decimal | None = None


class CostCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    cost_category_id: UUID
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    incurred_on: date | None = None
    notes: str | None = None
    receipt_filename: str | None = Field(default=None, max_length=255)


class CostItemRead(IDSchema):
    activity_id: UUID
    description: str
    cost_category: CatalogItemRead
    amount: Decimal
    currency: str
    incurred_on: date
    notes: str | None
    receipt_filename: str | None
    scope_type: ScopeType
    farm_id: UUID
    parcel_id: UUID | None
    row_id: UUID | None
    tree_id: UUID | None
    activity_title: str | None = None
    activity_type_name: str | None = None
    activity_line_items: list[QuantityLineRead] = Field(default_factory=list)
    parcel_name: str | None = None
    row_number: int | None = None
    tree_public_id: str | None = None


class NamedAmount(BaseModel):
    id: UUID
    name: str
    slug: str
    amount: Decimal


class YearAmount(BaseModel):
    year: int
    amount: Decimal


class CostSummaryRead(BaseModel):
    currency: str = "EUR"
    total_costs: Decimal
    current_year_costs: Decimal
    current_month_costs: Decimal
    cost_per_tree: Decimal | None
    cost_per_hectare: Decimal | None
    active_tree_count: int
    area_hectares: Decimal
    by_category: list[NamedAmount]
    by_activity_type: list[NamedAmount]
    by_year: list[YearAmount] = []
    parcel_id: UUID | None = None
    total_subsidies: Decimal = Decimal("0")
    subsidy_percent_of_costs: Decimal | None = None
