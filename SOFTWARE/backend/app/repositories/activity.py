from datetime import date
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.activity import Activity
from app.models.cost import Cost
from app.models.enums import ActivityStatus, ScopeType
from app.models.farm import Farm


class ActivityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[Activity]]:
        return (
            select(Activity)
            .join(Farm, Activity.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(
                selectinload(Activity.activity_type),
                selectinload(Activity.costs).selectinload(Cost.cost_category),
                selectinload(Activity.soil_analyses),
            )
        )

    def list_for_owner(
        self,
        owner_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        activity_type_id: UUID | None = None,
        scope_type: ScopeType | None = None,
        parcel_id: UUID | None = None,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        status: ActivityStatus | None = None,
        limit: int | None = None,
    ) -> list[Activity]:
        stmt = self._owned(owner_id)
        if date_from is not None:
            stmt = stmt.where(Activity.performed_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Activity.performed_on <= date_to)
        if activity_type_id is not None:
            stmt = stmt.where(Activity.activity_type_id == activity_type_id)
        if scope_type is not None:
            stmt = stmt.where(Activity.scope_type == scope_type)
        if parcel_id is not None:
            stmt = stmt.where(Activity.parcel_id == parcel_id)
        if row_id is not None:
            stmt = stmt.where(
                or_(
                    Activity.row_id == row_id,
                    Activity.extra_row_ids.contains([str(row_id)]),
                )
            )
        if tree_id is not None:
            stmt = stmt.where(Activity.tree_id == tree_id)
        if status is not None:
            stmt = stmt.where(Activity.status == status)
        stmt = stmt.order_by(Activity.performed_on.desc(), Activity.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).unique().all())

    def list_overlapping_scope(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID,
        row_id: UUID | None = None,
        tree_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        include_activity_id: UUID | None = None,
    ) -> list[Activity]:
        """One query: inherit parcel → row → tree without N+1 lookups."""
        stmt = self._owned(owner_id).where(Activity.parcel_id == parcel_id)
        if date_from is not None:
            stmt = stmt.where(Activity.performed_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(Activity.performed_on <= date_to)
        scope_filter = None
        if tree_id is not None and row_id is not None:
            scope_filter = or_(
                Activity.tree_id == tree_id,
                Activity.row_id == row_id,
                Activity.extra_row_ids.contains([str(row_id)]),
                Activity.scope_type == ScopeType.PARCEL,
            )
        elif row_id is not None:
            scope_filter = or_(
                Activity.row_id == row_id,
                Activity.extra_row_ids.contains([str(row_id)]),
                Activity.scope_type == ScopeType.PARCEL,
            )
        if include_activity_id is not None:
            extra = Activity.id == include_activity_id
            scope_filter = extra if scope_filter is None else or_(scope_filter, extra)
        if scope_filter is not None:
            stmt = stmt.where(scope_filter)
        stmt = stmt.order_by(Activity.performed_on.desc(), Activity.created_at.desc())
        return list(self.db.scalars(stmt).unique().all())

    def get_for_owner(self, activity_id: UUID, owner_id: UUID) -> Activity | None:
        stmt = self._owned(owner_id).where(Activity.id == activity_id)
        return self.db.scalars(stmt).unique().first()

    def count_for_farm(self, farm_id: UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Activity).where(Activity.farm_id == farm_id)
        return int(self.db.scalar(stmt) or 0)

    def add(self, activity: Activity) -> Activity:
        self.db.add(activity)
        return activity
