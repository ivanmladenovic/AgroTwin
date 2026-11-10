from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.models.enums import PassportStatus
from app.schemas.common import IDSchema, ORMModel

DEFAULT_VISIBILITY: dict[str, bool] = {
    "producer": True,
    "orchard": True,
    "location": True,
    "product": True,
    "quantity": True,
    "production_practices": True,
}


class PassportVisibility(ORMModel):
    producer: bool = True
    orchard: bool = True
    location: bool = True
    product: bool = True
    quantity: bool = True
    production_practices: bool = True


class HarvestLotCreate(ORMModel):
    harvest_id: UUID
    crop: str | None = Field(default=None, max_length=128)
    variety: str | None = Field(default=None, max_length=128)
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    visibility: PassportVisibility | None = None
    allow_indexing: bool = False
    finalize: bool = False


class HarvestLotUpdate(ORMModel):
    crop: str | None = Field(default=None, max_length=128)
    variety: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    visibility: PassportVisibility | None = None
    allow_indexing: bool | None = None


class HarvestLotRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID
    harvest_id: UUID
    lot_number: str
    harvest_date: date
    quantity: Decimal | None
    unit: str
    crop: str
    variety: str | None
    passport_token: str
    passport_status: PassportStatus
    visibility: dict[str, Any]
    allow_indexing: bool
    passport_version: str
    finalized_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by_id: UUID | None = None
    public_url: str
    qr_url: str
    parcel_name: str | None = None
    farm_name: str | None = None
    producer_name: str | None = None
    parcel_location: str | None = None
    varieties: list[str] = Field(default_factory=list)
    snapshot_version: int | None = None


class PublicProducerSection(ORMModel):
    name: str | None = None
    country: str | None = None
    logo_url: str | None = None


class PublicOrchardSection(ORMModel):
    farm_name: str | None = None
    location: str | None = None
    parcel_name: str | None = None


class PublicProductSection(ORMModel):
    crop: str | None = None
    variety: str | None = None
    varieties: list[str] = Field(default_factory=list)
    harvest_year: int | None = None
    harvest_date: date | None = None
    quantity: Decimal | None = None
    unit: str | None = None


class PublicPracticeItem(ORMModel):
    key: str
    label: str
    value: str


class PublicPassportRead(ORMModel):
    lot_number: str
    passport_version: str
    passport_status: PassportStatus
    created_at: datetime
    finalized: bool
    allow_indexing: bool
    producer: PublicProducerSection | None = None
    orchard: PublicOrchardSection | None = None
    product: PublicProductSection | None = None
    production_practices: list[PublicPracticeItem] | None = None
    traceability: list[str]
    metadata: dict[str, Any]
