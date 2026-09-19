from decimal import Decimal
from uuid import UUID

from app.schemas.common import IDSchema
from app.schemas.parcel import ParcelRead


class FarmRead(IDSchema):
    owner_id: UUID
    name: str
    description: str | None
    location_name: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    area_hectares: Decimal | None


class FarmDetail(FarmRead):
    parcels: list[ParcelRead]
