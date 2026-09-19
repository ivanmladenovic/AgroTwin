from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.activity import Activity, ActivityType
from app.models.cost import Cost, CostCategory
from app.models.farm import Farm


class CostRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[Cost]]:
        return (
            select(Cost)
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(
                selectinload(Cost.cost_category),
                selectinload(Cost.activity).selectinload(Activity.activity_type),
            )
        )

    def get_for_owner(self, cost_id: UUID, owner_id: UUID) -> Cost | None:
        stmt = self._owned(owner_id).where(Cost.id == cost_id)
        return self.db.scalars(stmt).unique().first()

    def list_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Cost]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Cost.incurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Cost.incurred_on <= date_to)
        stmt = stmt.order_by(Cost.incurred_on.desc(), Cost.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def sum_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        tree_id: UUID | None = None,
        row_id: UUID | None = None,
        exclude_tree_scope: bool = False,
    ) -> Decimal:
        stmt = (
            select(func.coalesce(func.sum(Cost.amount), 0))
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Cost.incurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Cost.incurred_on <= date_to)
        if tree_id is not None:
            stmt = stmt.where(Cost.tree_id == tree_id)
        if row_id is not None:
            stmt = stmt.where(Cost.row_id == row_id)
        if exclude_tree_scope:
            from app.models.enums import ScopeType

            stmt = stmt.where(Cost.scope_type != ScopeType.TREE)
        return Decimal(self.db.scalar(stmt) or 0)

    def totals_by_category(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[tuple[CostCategory, Decimal]]:
        stmt = (
            select(CostCategory, func.coalesce(func.sum(Cost.amount), 0))
            .join(Cost, Cost.cost_category_id == CostCategory.id)
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .group_by(CostCategory.id)
            .order_by(func.sum(Cost.amount).desc(), CostCategory.sort_order)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Cost.incurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Cost.incurred_on <= date_to)
        return [(category, Decimal(total)) for category, total in self.db.execute(stmt).all()]

    def monthly_totals(
        self,
        owner_id: UUID,
        *,
        year: int,
        parcel_id: UUID | None = None,
    ) -> dict[int, Decimal]:
        from sqlalchemy import extract

        month_col = extract("month", Cost.incurred_on)
        year_col = extract("year", Cost.incurred_on)
        stmt = (
            select(month_col, func.coalesce(func.sum(Cost.amount), 0))
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id, year_col == year)
            .group_by(month_col)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        totals: dict[int, Decimal] = {}
        for month, total in self.db.execute(stmt).all():
            totals[int(month)] = Decimal(total)
        return totals

    def yearly_totals(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
    ) -> dict[int, Decimal]:
        year_col = extract("year", Cost.incurred_on)
        stmt = (
            select(year_col, func.coalesce(func.sum(Cost.amount), 0))
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .group_by(year_col)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        totals: dict[int, Decimal] = {}
        for year, total in self.db.execute(stmt).all():
            totals[int(year)] = Decimal(total)
        return totals

    def totals_by_activity_type(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[tuple[ActivityType, Decimal]]:
        stmt = (
            select(ActivityType, func.coalesce(func.sum(Cost.amount), 0))
            .join(Activity, Activity.activity_type_id == ActivityType.id)
            .join(Cost, Cost.activity_id == Activity.id)
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .group_by(ActivityType.id)
            .order_by(func.sum(Cost.amount).desc(), ActivityType.sort_order)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Cost.incurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Cost.incurred_on <= date_to)
        return [(activity_type, Decimal(total)) for activity_type, total in self.db.execute(stmt).all()]

    def exists_for_owner(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> bool:
        stmt = (
            select(Cost.id)
            .join(Farm, Cost.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .limit(1)
        )
        if parcel_id is not None:
            stmt = stmt.where(Cost.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Cost.incurred_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Cost.incurred_on <= date_to)
        return self.db.scalar(stmt) is not None

    def add(self, cost: Cost) -> Cost:
        self.db.add(cost)
        return cost
