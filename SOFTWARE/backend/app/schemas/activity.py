from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ActivityStatus, ScopeType
from app.schemas.catalog import CatalogItemRead
from app.schemas.common import IDSchema
from app.schemas.cost import CostItemRead
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


class ActivityUpdate(BaseModel):
    status: ActivityStatus | None = None
    performed_on: date | None = None
    notes: str | None = None
    description: str | None = None


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
    total_cost: Decimal
    currency: str = "EUR"
