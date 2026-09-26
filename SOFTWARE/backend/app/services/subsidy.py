from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.subsidy import Subsidy
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.subsidy import SubsidyRepository
from app.schemas.subsidy import SubsidyCreate, SubsidyRead, SubsidyUpdate


class SubsidyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.subsidies = SubsidyRepository(db)
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)

    def list_subsidies(self, owner_id: UUID, parcel_id: UUID | None = None) -> list[SubsidyRead]:
        if parcel_id is not None:
            parcel = self.parcels.get_for_owner(parcel_id, owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
        items = self.subsidies.list_for_owner(owner_id, parcel_id=parcel_id)
        names: dict[UUID, str] = {}
        parcel_ids = [item.parcel_id for item in items if item.parcel_id is not None]
        if parcel_ids:
            for parcel in self.parcels.list_for_owner(owner_id):
                if parcel.id in parcel_ids:
                    names[parcel.id] = parcel.name
        return [self.to_read(item, parcel_name=names.get(item.parcel_id) if item.parcel_id else None) for item in items]

    def create(self, owner_id: UUID, payload: SubsidyCreate, created_by_id: UUID) -> Subsidy:
        farm = self._farm(owner_id)
        parcel_id = self._parcel_id(owner_id, payload.parcel_id)
        subsidy = Subsidy(
            farm_id=farm.id,
            parcel_id=parcel_id,
            title=payload.title.strip(),
            total_cost=payload.total_cost.quantize(Decimal("0.01")),
            subsidy_amount=payload.subsidy_amount.quantize(Decimal("0.01")),
            currency=payload.currency.upper(),
            received_on=payload.received_on,
            notes=(payload.notes or "").strip() or None,
            created_by_id=created_by_id,
        )
        self.subsidies.add(subsidy)
        self.db.commit()
        self.db.refresh(subsidy)
        return subsidy

    def update(self, subsidy_id: UUID, owner_id: UUID, payload: SubsidyUpdate) -> Subsidy:
        subsidy = self._get(subsidy_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "parcel_id" in data:
            subsidy.parcel_id = self._parcel_id(owner_id, data.pop("parcel_id"))
        if "title" in data and data["title"] is not None:
            subsidy.title = data["title"].strip()
        if "notes" in data:
            subsidy.notes = (data["notes"] or "").strip() or None
        if "received_on" in data and data["received_on"] is not None:
            subsidy.received_on = data["received_on"]
        if "total_cost" in data and data["total_cost"] is not None:
            subsidy.total_cost = data["total_cost"].quantize(Decimal("0.01"))
        if "subsidy_amount" in data and data["subsidy_amount"] is not None:
            subsidy.subsidy_amount = data["subsidy_amount"].quantize(Decimal("0.01"))
        if subsidy.subsidy_amount > subsidy.total_cost:
            raise AppError("Iznos subvencije ne može biti veći od ukupnog troška.", status_code=422, code="invalid_amount")
        self.db.commit()
        self.db.refresh(subsidy)
        return subsidy

    def delete(self, subsidy_id: UUID, owner_id: UUID) -> None:
        subsidy = self._get(subsidy_id, owner_id)
        self.subsidies.delete(subsidy)
        self.db.commit()

    def to_read(self, subsidy: Subsidy, parcel_name: str | None = None) -> SubsidyRead:
        if parcel_name is None and subsidy.parcel_id is not None:
            parcel = self.parcels.get_by_id(subsidy.parcel_id)
            parcel_name = parcel.name if parcel else None
        return SubsidyRead(
            id=subsidy.id,
            created_at=subsidy.created_at,
            updated_at=subsidy.updated_at,
            farm_id=subsidy.farm_id,
            parcel_id=subsidy.parcel_id,
            parcel_name=parcel_name,
            title=subsidy.title,
            total_cost=subsidy.total_cost,
            subsidy_amount=subsidy.subsidy_amount,
            subsidy_percent=_percent(subsidy.subsidy_amount, subsidy.total_cost),
            currency=subsidy.currency,
            received_on=subsidy.received_on,
            notes=subsidy.notes,
            created_by_id=subsidy.created_by_id,
        )

    def _get(self, subsidy_id: UUID, owner_id: UUID) -> Subsidy:
        subsidy = self.subsidies.get_for_owner(subsidy_id, owner_id)
        if subsidy is None:
            raise NotFoundError("Subvencija nije pronađena")
        return subsidy

    def _farm(self, owner_id: UUID):
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def _parcel_id(self, owner_id: UUID, parcel_id: UUID | None) -> UUID | None:
        if parcel_id is None:
            return None
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel.id


def _percent(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole <= 0:
        return None
    return (part / whole * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
