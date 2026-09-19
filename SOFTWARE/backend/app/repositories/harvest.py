from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ScopeType
from app.models.farm import Farm
from app.models.harvest import HarvestEvent
from app.models.row import Row
from app.models.tree import Tree


class HarvestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[HarvestEvent]]:
        return (
            select(HarvestEvent)
            .join(Farm, HarvestEvent.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(selectinload(HarvestEvent.created_by))
        )

    def list_for_parcel(
        self,
        owner_id: UUID,
        parcel_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        scope_type: ScopeType | None = None,
    ) -> list[HarvestEvent]:
        stmt = self._owned(owner_id).where(HarvestEvent.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(HarvestEvent.harvested_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(HarvestEvent.harvested_on <= date_to)
        if scope_type is not None:
            stmt = stmt.where(HarvestEvent.scope_type == scope_type)
        stmt = stmt.order_by(HarvestEvent.harvested_on.asc(), HarvestEvent.created_at.asc())
        return list(self.db.scalars(stmt).unique().all())

    def get_for_owner(self, harvest_id: UUID, owner_id: UUID) -> HarvestEvent | None:
        stmt = self._owned(owner_id).where(HarvestEvent.id == harvest_id)
        return self.db.scalars(stmt).unique().first()

    def years_for_parcel(self, parcel_id: UUID) -> list[int]:
        stmt = (
            select(extract("year", HarvestEvent.harvested_on))
            .where(HarvestEvent.parcel_id == parcel_id)
            .distinct()
        )
        return [int(year) for year in self.db.scalars(stmt).all() if year is not None]

    def row_totals(
        self,
        parcel_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[tuple[UUID, Decimal, int]]:
        stmt = (
            select(
                HarvestEvent.row_id,
                func.coalesce(func.sum(HarvestEvent.net_quantity), 0),
                func.count(),
            )
            .where(
                HarvestEvent.parcel_id == parcel_id,
                HarvestEvent.scope_type == ScopeType.ROW,
                HarvestEvent.harvested_on >= date_from,
                HarvestEvent.harvested_on <= date_to,
                HarvestEvent.row_id.is_not(None),
                HarvestEvent.unit == "kg",
            )
            .group_by(HarvestEvent.row_id)
        )
        return [(row_id, Decimal(str(total)), int(count)) for row_id, total, count in self.db.execute(stmt).all() if row_id]

    def tree_totals(
        self,
        parcel_id: UUID,
        date_from: date,
        date_to: date,
    ) -> list[tuple[UUID, Decimal, int]]:
        stmt = (
            select(
                HarvestEvent.tree_id,
                func.coalesce(func.sum(HarvestEvent.net_quantity), 0),
                func.count(),
            )
            .where(
                HarvestEvent.parcel_id == parcel_id,
                HarvestEvent.scope_type == ScopeType.TREE,
                HarvestEvent.harvested_on >= date_from,
                HarvestEvent.harvested_on <= date_to,
                HarvestEvent.tree_id.is_not(None),
                HarvestEvent.unit == "kg",
            )
            .group_by(HarvestEvent.tree_id)
        )
        return [(tree_id, Decimal(str(total)), int(count)) for tree_id, total, count in self.db.execute(stmt).all() if tree_id]

    def exists_in_range(self, parcel_id: UUID, date_from: date, date_to: date) -> bool:
        stmt = (
            select(HarvestEvent.id)
            .where(
                HarvestEvent.parcel_id == parcel_id,
                HarvestEvent.harvested_on >= date_from,
                HarvestEvent.harvested_on <= date_to,
            )
            .limit(1)
        )
        return self.db.scalar(stmt) is not None

    def add(self, event: HarvestEvent) -> HarvestEvent:
        self.db.add(event)
        return event

    def delete(self, event: HarvestEvent) -> None:
        self.db.delete(event)


def row_numbers_by_id(db: Session, parcel_id: UUID) -> dict[UUID, int]:
    stmt = select(Row.id, Row.row_number).where(Row.parcel_id == parcel_id)
    return {row_id: number for row_id, number in db.execute(stmt).all()}


def trees_by_id(db: Session, tree_ids: list[UUID]) -> dict[UUID, Tree]:
    if not tree_ids:
        return {}
    stmt = select(Tree).where(Tree.id.in_(tree_ids))
    return {tree.id: tree for tree in db.scalars(stmt).all()}
