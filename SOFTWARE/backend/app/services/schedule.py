from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.activity import Activity
from app.models.enums import ActivityStatus, ScopeType
from app.models.schedule import OrchardSeason, TaskSchedule
from app.repositories.catalog import CatalogRepository
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.schedule import ScheduleRepository, SeasonRepository
from app.schemas.catalog import CatalogItemRead
from app.schemas.schedule import (
    OrchardSeasonCreate,
    OrchardSeasonRead,
    OrchardSeasonUpdate,
    TaskScheduleCreate,
    TaskScheduleRead,
    TaskScheduleUpdate,
)

WEEKDAY_LABELS = ("ponedeljak", "utorak", "sreda", "četvrtak", "petak", "subota", "nedelja")


class ScheduleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.seasons = SeasonRepository(db)
        self.schedules = ScheduleRepository(db)
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.catalogs = CatalogRepository(db)

    # --- seasons ---

    def list_seasons(self, owner_id: UUID, parcel_id: UUID | None = None) -> list[OrchardSeasonRead]:
        if parcel_id is not None:
            self._parcel(owner_id, parcel_id)
        return [self.to_season_read(item) for item in self.seasons.list_for_owner(owner_id, parcel_id=parcel_id)]

    def create_season(self, owner_id: UUID, payload: OrchardSeasonCreate, created_by_id: UUID) -> OrchardSeason:
        farm = self._farm(owner_id)
        season = OrchardSeason(
            farm_id=farm.id,
            parcel_id=self._parcel_id(owner_id, payload.parcel_id),
            name=payload.name.strip(),
            starts_on=payload.starts_on,
            ends_on=payload.ends_on,
            notes=(payload.notes or "").strip() or None,
            created_by_id=created_by_id,
        )
        self.seasons.add(season)
        self.db.commit()
        self.db.refresh(season)
        return season

    def update_season(self, season_id: UUID, owner_id: UUID, payload: OrchardSeasonUpdate) -> OrchardSeason:
        season = self._get_season(season_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "parcel_id" in data:
            season.parcel_id = self._parcel_id(owner_id, data.pop("parcel_id"))
        if "name" in data and data["name"] is not None:
            season.name = data["name"].strip()
        if "notes" in data:
            season.notes = (data["notes"] or "").strip() or None
        if "starts_on" in data and data["starts_on"] is not None:
            season.starts_on = data["starts_on"]
        if "ends_on" in data and data["ends_on"] is not None:
            season.ends_on = data["ends_on"]
        if season.ends_on < season.starts_on:
            raise AppError("Kraj sezone ne može biti pre početka.", status_code=422, code="invalid_range")
        self.db.commit()
        self.db.refresh(season)
        # Refresh linked schedules' windows if they still point at this season
        for schedule in self.schedules.list_for_owner(owner_id):
            if schedule.season_id == season.id:
                schedule.starts_on = season.starts_on
                schedule.ends_on = season.ends_on
                if schedule.parcel_id is None and season.parcel_id is not None:
                    schedule.parcel_id = season.parcel_id
                self._sync_activities(schedule)
        self.db.commit()
        return season

    def delete_season(self, season_id: UUID, owner_id: UUID) -> None:
        season = self._get_season(season_id, owner_id)
        self.seasons.delete(season)
        self.db.commit()

    def to_season_read(self, season: OrchardSeason) -> OrchardSeasonRead:
        parcel_name = None
        if season.parcel_id is not None:
            parcel = self.parcels.get_by_id(season.parcel_id)
            parcel_name = parcel.name if parcel else None
        return OrchardSeasonRead(
            id=season.id,
            created_at=season.created_at,
            updated_at=season.updated_at,
            farm_id=season.farm_id,
            parcel_id=season.parcel_id,
            parcel_name=parcel_name,
            name=season.name,
            starts_on=season.starts_on,
            ends_on=season.ends_on,
            notes=season.notes,
            created_by_id=season.created_by_id,
        )

    # --- schedules ---

    def list_schedules(self, owner_id: UUID, parcel_id: UUID | None = None) -> list[TaskScheduleRead]:
        if parcel_id is not None:
            self._parcel(owner_id, parcel_id)
        return [self.to_schedule_read(item) for item in self.schedules.list_for_owner(owner_id, parcel_id=parcel_id)]

    def create_schedule(self, owner_id: UUID, payload: TaskScheduleCreate, created_by_id: UUID) -> TaskSchedule:
        farm = self._farm(owner_id)
        activity_type = self.catalogs.get_activity_type(payload.activity_type_id)
        if activity_type is None:
            raise NotFoundError("Tip aktivnosti nije pronađen")
        starts_on, ends_on, season_id, parcel_id = self._resolve_window(owner_id, payload)
        if parcel_id is None:
            parcel_id = self._default_parcel_id(farm.id)
        if parcel_id is None:
            raise AppError(
                "Raspored zahteva parcelu. Prvo dodajte parcelu.",
                status_code=422,
                code="missing_parcel",
            )
        dates = occurrence_dates(starts_on, ends_on, payload.weekdays)
        if payload.is_active and not dates:
            raise AppError(
                "Nijedan dan u periodu ne odgovara izabranim danima u nedelji.",
                status_code=422,
                code="empty_schedule",
            )
        schedule = TaskSchedule(
            farm_id=farm.id,
            parcel_id=parcel_id,
            season_id=season_id,
            activity_type_id=activity_type.id,
            title=payload.title.strip(),
            starts_on=starts_on,
            ends_on=ends_on,
            weekdays=payload.weekdays,
            notes=(payload.notes or "").strip() or None,
            is_active=payload.is_active,
            created_by_id=created_by_id,
        )
        self.schedules.add(schedule)
        self.db.flush()
        self._sync_activities(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update_schedule(self, schedule_id: UUID, owner_id: UUID, payload: TaskScheduleUpdate) -> TaskSchedule:
        schedule = self._get_schedule(schedule_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "parcel_id" in data:
            schedule.parcel_id = self._parcel_id(owner_id, data.pop("parcel_id"))
        if "season_id" in data:
            season_id = data.pop("season_id")
            if season_id is None:
                schedule.season_id = None
            else:
                season = self._get_season(season_id, owner_id)
                schedule.season_id = season.id
                schedule.starts_on = season.starts_on
                schedule.ends_on = season.ends_on
                if schedule.parcel_id is None and season.parcel_id is not None:
                    schedule.parcel_id = season.parcel_id
        if "activity_type_id" in data and data["activity_type_id"] is not None:
            activity_type = self.catalogs.get_activity_type(data["activity_type_id"])
            if activity_type is None:
                raise NotFoundError("Tip aktivnosti nije pronađen")
            schedule.activity_type_id = activity_type.id
        if "title" in data and data["title"] is not None:
            schedule.title = data["title"].strip()
        if "notes" in data:
            schedule.notes = (data["notes"] or "").strip() or None
        if "weekdays" in data and data["weekdays"] is not None:
            schedule.weekdays = data["weekdays"]
        if "starts_on" in data and data["starts_on"] is not None:
            schedule.starts_on = data["starts_on"]
        if "ends_on" in data and data["ends_on"] is not None:
            schedule.ends_on = data["ends_on"]
        if "is_active" in data and data["is_active"] is not None:
            schedule.is_active = data["is_active"]
        if schedule.ends_on < schedule.starts_on:
            raise AppError("Kraj perioda ne može biti pre početka.", status_code=422, code="invalid_range")
        self._sync_activities(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete_schedule(self, schedule_id: UUID, owner_id: UUID) -> None:
        schedule = self._get_schedule(schedule_id, owner_id)
        # Remove only future/remaining planned occurrences; keep completed history
        self.schedules.delete_planned_except_dates(schedule.id, set())
        self.schedules.delete(schedule)
        self.db.commit()

    def to_schedule_read(self, schedule: TaskSchedule) -> TaskScheduleRead:
        parcel_name = None
        if schedule.parcel_id is not None:
            parcel = self.parcels.get_by_id(schedule.parcel_id)
            parcel_name = parcel.name if parcel else None
        season_name = schedule.season.name if schedule.season is not None else None
        return TaskScheduleRead(
            id=schedule.id,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            farm_id=schedule.farm_id,
            parcel_id=schedule.parcel_id,
            parcel_name=parcel_name,
            season_id=schedule.season_id,
            season_name=season_name,
            activity_type=CatalogItemRead.model_validate(schedule.activity_type),
            title=schedule.title,
            starts_on=schedule.starts_on,
            ends_on=schedule.ends_on,
            weekdays=list(schedule.weekdays or []),
            notes=schedule.notes,
            is_active=schedule.is_active,
            created_by_id=schedule.created_by_id,
            planned_count=self.schedules.count_planned(schedule.id),
        )

    def _sync_activities(self, schedule: TaskSchedule) -> int:
        """Create/update planned activities for matching weekdays; leave completed alone."""
        if not schedule.is_active:
            self.schedules.delete_planned_except_dates(schedule.id, set())
            return 0

        target_dates = occurrence_dates(schedule.starts_on, schedule.ends_on, schedule.weekdays)
        existing = self.schedules.existing_dates(schedule.id)
        self.schedules.delete_planned_except_dates(schedule.id, target_dates)

        # Keep planned rows in sync with current title/type/notes
        for activity in self.schedules.planned_for_schedule(schedule.id):
            activity.title = schedule.title
            activity.activity_type_id = schedule.activity_type_id
            activity.description = schedule.notes
            activity.parcel_id = schedule.parcel_id

        created = 0
        parcel_id = schedule.parcel_id or self._default_parcel_id(schedule.farm_id)
        if parcel_id is None:
            raise AppError(
                "Raspored zahteva parcelu. Izaberite parcelu ili dodajte parcelu na gazdinstvo.",
                status_code=422,
                code="missing_parcel",
            )
        schedule.parcel_id = parcel_id
        for day in target_dates:
            if day in existing:
                continue
            activity = Activity(
                activity_type_id=schedule.activity_type_id,
                title=schedule.title,
                description=schedule.notes,
                performed_on=day,
                status=ActivityStatus.PLANNED,
                line_items=[],
                extra_row_ids=[],
                notes=None,
                created_by_id=schedule.created_by_id,
                schedule_id=schedule.id,
                scope_type=ScopeType.PARCEL,
                farm_id=schedule.farm_id,
                parcel_id=parcel_id,
                row_id=None,
                tree_id=None,
            )
            self.db.add(activity)
            created += 1
        return created

    def _resolve_window(
        self, owner_id: UUID, payload: TaskScheduleCreate
    ) -> tuple[date, date, UUID | None, UUID | None]:
        parcel_id = self._parcel_id(owner_id, payload.parcel_id)
        if payload.season_id is not None:
            season = self._get_season(payload.season_id, owner_id)
            return (
                season.starts_on,
                season.ends_on,
                season.id,
                parcel_id if parcel_id is not None else season.parcel_id,
            )
        if payload.whole_year:
            year = payload.year or date.today().year
            return date(year, 1, 1), date(year, 12, 31), None, parcel_id
        assert payload.starts_on is not None and payload.ends_on is not None
        return payload.starts_on, payload.ends_on, None, parcel_id

    def _default_parcel_id(self, farm_id: UUID) -> UUID | None:
        parcels = self.parcels.list_by_farm(farm_id)
        return parcels[0].id if parcels else None

    def _get_season(self, season_id: UUID, owner_id: UUID) -> OrchardSeason:
        season = self.seasons.get_for_owner(season_id, owner_id)
        if season is None:
            raise NotFoundError("Sezona nije pronađena")
        return season

    def _get_schedule(self, schedule_id: UUID, owner_id: UUID) -> TaskSchedule:
        schedule = self.schedules.get_for_owner(schedule_id, owner_id)
        if schedule is None:
            raise NotFoundError("Raspored nije pronađen")
        return schedule

    def _farm(self, owner_id: UUID):
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def _parcel(self, owner_id: UUID, parcel_id: UUID):
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        return parcel

    def _parcel_id(self, owner_id: UUID, parcel_id: UUID | None) -> UUID | None:
        if parcel_id is None:
            return None
        return self._parcel(owner_id, parcel_id).id


def occurrence_dates(starts_on: date, ends_on: date, weekdays: list[int]) -> list[date]:
    wanted = set(weekdays)
    days: list[date] = []
    cursor = starts_on
    while cursor <= ends_on:
        if cursor.weekday() in wanted:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days
