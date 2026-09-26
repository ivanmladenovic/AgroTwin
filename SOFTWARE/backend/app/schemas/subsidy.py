from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import IDSchema


class SubsidyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    total_cost: Decimal = Field(gt=0)
    subsidy_amount: Decimal = Field(ge=0)
    received_on: date
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)
    currency: str = Field(default="EUR", min_length=3, max_length=3)

    @model_validator(mode="after")
    def amount_within_total(self) -> "SubsidyCreate":
        if self.subsidy_amount > self.total_cost:
            raise ValueError("Iznos subvencije ne može biti veći od ukupnog troška.")
        return self


class SubsidyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    total_cost: Decimal | None = Field(default=None, gt=0)
    subsidy_amount: Decimal | None = Field(default=None, ge=0)
    received_on: date | None = None
    parcel_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class SubsidyRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID | None
    parcel_name: str | None = None
    title: str
    total_cost: Decimal
    subsidy_amount: Decimal
    subsidy_percent: Decimal | None
    currency: str
    received_on: date
    notes: str | None
    created_by_id: UUID | None
