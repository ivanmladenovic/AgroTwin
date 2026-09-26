from datetime import date
from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.activity import Activity
from app.models.enums import ActivityStatus
from app.models.farm import Farm
from app.models.schedule import OrchardSeason, TaskSchedule


class SeasonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[OrchardSeason]]:
        return (
            select(OrchardSeason)
            .join(Farm, OrchardSeason.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def list_for_owner(self, owner_id: UUID, *, parcel_id: UUID | None = None) -> list[OrchardSeason]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(OrchardSeason.parcel_id == parcel_id)
        stmt = stmt.order_by(OrchardSeason.starts_on.desc(), OrchardSeason.name)
        return list(self.db.scalars(stmt).all())

    def get_for_owner(self, season_id: UUID, owner_id: UUID) -> OrchardSeason | None:
        return self.db.scalars(self._owned(owner_id).where(OrchardSeason.id == season_id)).first()

    def add(self, season: OrchardSeason) -> OrchardSeason:
        self.db.add(season)
        return season

    def delete(self, season: OrchardSeason) -> None:
        self.db.delete(season)


class ScheduleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _owned(self, owner_id: UUID) -> Select[tuple[TaskSchedule]]:
        return (
            select(TaskSchedule)
            .options(selectinload(TaskSchedule.activity_type), selectinload(TaskSchedule.season))
            .join(Farm, TaskSchedule.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def list_for_owner(self, owner_id: UUID, *, parcel_id: UUID | None = None) -> list[TaskSchedule]:
        stmt = self._owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(TaskSchedule.parcel_id == parcel_id)
        stmt = stmt.order_by(TaskSchedule.starts_on.desc(), TaskSchedule.title)
        return list(self.db.scalars(stmt).all())

    def get_for_owner(self, schedule_id: UUID, owner_id: UUID) -> TaskSchedule | None:
        return self.db.scalars(self._owned(owner_id).where(TaskSchedule.id == schedule_id)).first()

    def add(self, schedule: TaskSchedule) -> TaskSchedule:
        self.db.add(schedule)
        return schedule

    def delete(self, schedule: TaskSchedule) -> None:
        self.db.delete(schedule)

    def planned_for_schedule(self, schedule_id: UUID) -> list[Activity]:
        stmt = select(Activity).where(
            Activity.schedule_id == schedule_id,
            Activity.status == ActivityStatus.PLANNED,
        )
        return list(self.db.scalars(stmt).all())

    def count_planned(self, schedule_id: UUID) -> int:
        from sqlalchemy import func

        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Activity)
                .where(Activity.schedule_id == schedule_id, Activity.status == ActivityStatus.PLANNED)
            )
            or 0
        )

    def delete_planned_except_dates(self, schedule_id: UUID, keep_dates: set[date]) -> None:
        stmt = delete(Activity).where(
            Activity.schedule_id == schedule_id,
            Activity.status == ActivityStatus.PLANNED,
        )
        if keep_dates:
            stmt = stmt.where(Activity.performed_on.notin_(sorted(keep_dates)))
        self.db.execute(stmt)

    def existing_dates(self, schedule_id: UUID) -> set[date]:
        rows = self.db.scalars(
            select(Activity.performed_on).where(Activity.schedule_id == schedule_id)
        ).all()
        return set(rows)
