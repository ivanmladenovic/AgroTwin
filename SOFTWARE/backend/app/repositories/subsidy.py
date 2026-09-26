from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.subsidy import Subsidy


class SubsidyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[Subsidy]]:
        return (
            select(Subsidy)
            .join(Farm, Subsidy.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def list_for_owner(self, owner_id: UUID, *, parcel_id: UUID | None = None) -> list[Subsidy]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(Subsidy.parcel_id == parcel_id)
        stmt = stmt.order_by(Subsidy.received_on.desc(), Subsidy.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_for_owner(self, subsidy_id: UUID, owner_id: UUID) -> Subsidy | None:
        stmt = self._owned(owner_id).where(Subsidy.id == subsidy_id)
        return self.db.scalars(stmt).first()

    def sum_for_owner(self, owner_id: UUID, *, parcel_id: UUID | None = None) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Subsidy.subsidy_amount), 0))
            .join(Farm, Subsidy.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )
        if parcel_id is not None:
            stmt = stmt.where(Subsidy.parcel_id == parcel_id)
        return Decimal(self.db.scalar(stmt) or 0)

    def add(self, subsidy: Subsidy) -> Subsidy:
        self.db.add(subsidy)
        return subsidy

    def delete(self, subsidy: Subsidy) -> None:
        self.db.delete(subsidy)
