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

    def list_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_farm_wide: bool = True,
    ) -> list[Subsidy]:
        from sqlalchemy import or_

        stmt = self._owned(owner_id)
        if parcel_id is not None:
            if include_farm_wide:
                stmt = stmt.where(or_(Subsidy.parcel_id == parcel_id, Subsidy.parcel_id.is_(None)))
            else:
                stmt = stmt.where(Subsidy.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Subsidy.received_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Subsidy.received_on <= date_to)
        stmt = stmt.order_by(Subsidy.received_on.desc(), Subsidy.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_for_owner(self, subsidy_id: UUID, owner_id: UUID) -> Subsidy | None:
        stmt = self._owned(owner_id).where(Subsidy.id == subsidy_id)
        return self.db.scalars(stmt).first()

    def list_by_activity_ids(self, activity_ids: list[UUID]) -> list[Subsidy]:
        if not activity_ids:
            return []
        stmt = select(Subsidy).where(Subsidy.activity_id.in_(activity_ids))
        return list(self.db.scalars(stmt).all())

    def list_missing_activity(self, owner_id: UUID) -> list[Subsidy]:
        stmt = self._owned(owner_id).where(Subsidy.activity_id.is_(None))
        return list(self.db.scalars(stmt).all())

    def sum_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_farm_wide: bool = True,
    ) -> Decimal:
        from sqlalchemy import or_

        stmt = (
            select(func.coalesce(func.sum(Subsidy.subsidy_amount), 0))
            .join(Farm, Subsidy.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )
        if parcel_id is not None:
            if include_farm_wide:
                stmt = stmt.where(or_(Subsidy.parcel_id == parcel_id, Subsidy.parcel_id.is_(None)))
            else:
                stmt = stmt.where(Subsidy.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Subsidy.received_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Subsidy.received_on <= date_to)
        return Decimal(self.db.scalar(stmt) or 0)

    def add(self, subsidy: Subsidy) -> Subsidy:
        self.db.add(subsidy)
        return subsidy

    def delete(self, subsidy: Subsidy) -> None:
        self.db.delete(subsidy)
