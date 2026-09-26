from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.schedule import (
    OrchardSeasonCreate,
    OrchardSeasonRead,
    OrchardSeasonUpdate,
    TaskScheduleCreate,
    TaskScheduleRead,
    TaskScheduleUpdate,
)
from app.services.schedule import ScheduleService

router = APIRouter(tags=["schedules"])


@router.get("/seasons", response_model=list[OrchardSeasonRead])
def list_seasons(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
) -> list[OrchardSeasonRead]:
    return ScheduleService(db).list_seasons(current_user.id, parcel_id)


@router.post("/seasons", response_model=OrchardSeasonRead, status_code=201)
def create_season(payload: OrchardSeasonCreate, current_user: CurrentUser, db: DBSession) -> OrchardSeasonRead:
    service = ScheduleService(db)
    season = service.create_season(current_user.id, payload, current_user.id)
    return service.to_season_read(season)


@router.patch("/seasons/{season_id}", response_model=OrchardSeasonRead)
def update_season(
    season_id: UUID,
    payload: OrchardSeasonUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> OrchardSeasonRead:
    service = ScheduleService(db)
    season = service.update_season(season_id, current_user.id, payload)
    return service.to_season_read(season)


@router.delete("/seasons/{season_id}", status_code=204)
def delete_season(season_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    ScheduleService(db).delete_season(season_id, current_user.id)


@router.get("/schedules", response_model=list[TaskScheduleRead])
def list_schedules(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
) -> list[TaskScheduleRead]:
    return ScheduleService(db).list_schedules(current_user.id, parcel_id)


@router.post("/schedules", response_model=TaskScheduleRead, status_code=201)
def create_schedule(payload: TaskScheduleCreate, current_user: CurrentUser, db: DBSession) -> TaskScheduleRead:
    service = ScheduleService(db)
    schedule = service.create_schedule(current_user.id, payload, current_user.id)
    return service.to_schedule_read(schedule)


@router.patch("/schedules/{schedule_id}", response_model=TaskScheduleRead)
def update_schedule(
    schedule_id: UUID,
    payload: TaskScheduleUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> TaskScheduleRead:
    service = ScheduleService(db)
    schedule = service.update_schedule(schedule_id, current_user.id, payload)
    return service.to_schedule_read(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    ScheduleService(db).delete_schedule(schedule_id, current_user.id)
