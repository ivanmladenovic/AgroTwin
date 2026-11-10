from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.models.enums import WorkTaskStatus
from app.schemas.catalog import CatalogItemRead
from app.schemas.workforce import (
    ParcelLaborSummary,
    WorkTaskCreate,
    WorkTaskRead,
    WorkTaskUpdate,
    WorkerCreate,
    WorkerRead,
    WorkerUpdate,
    WorkforceDashboard,
)
from app.services.workforce import WorkforceService

router = APIRouter(tags=["workforce"])


@router.get("/work-task-types", response_model=list[CatalogItemRead])
def list_work_task_types(_current_user: CurrentUser, db: DBSession) -> list[CatalogItemRead]:
    return WorkforceService(db).list_task_types()


@router.get("/workers", response_model=list[WorkerRead])
def list_workers(
    current_user: CurrentUser,
    db: DBSession,
    active_only: bool = Query(default=False),
) -> list[WorkerRead]:
    return WorkforceService(db).list_workers(current_user.id, active_only=active_only)


@router.post("/workers", response_model=WorkerRead, status_code=201)
def create_worker(payload: WorkerCreate, current_user: CurrentUser, db: DBSession) -> WorkerRead:
    return WorkforceService(db).create_worker(current_user.id, payload, current_user.id)


@router.patch("/workers/{worker_id}", response_model=WorkerRead)
def update_worker(
    worker_id: UUID,
    payload: WorkerUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> WorkerRead:
    return WorkforceService(db).update_worker(worker_id, current_user.id, payload)


@router.delete("/workers/{worker_id}", status_code=204)
def delete_worker(worker_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    WorkforceService(db).delete_worker(worker_id, current_user.id)


@router.get("/work-tasks", response_model=list[WorkTaskRead])
def list_work_tasks(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
    worker_id: UUID | None = None,
    task_type_id: UUID | None = None,
    status: WorkTaskStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[WorkTaskRead]:
    return WorkforceService(db).list_tasks(
        current_user.id,
        parcel_id=parcel_id,
        worker_id=worker_id,
        task_type_id=task_type_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/work-tasks", response_model=WorkTaskRead, status_code=201)
def create_work_task(payload: WorkTaskCreate, current_user: CurrentUser, db: DBSession) -> WorkTaskRead:
    return WorkforceService(db).create_task(current_user.id, payload, current_user.id)


@router.get("/work-tasks/{task_id}", response_model=WorkTaskRead)
def get_work_task(task_id: UUID, current_user: CurrentUser, db: DBSession) -> WorkTaskRead:
    return WorkforceService(db).get_task(task_id, current_user.id)


@router.patch("/work-tasks/{task_id}", response_model=WorkTaskRead)
def update_work_task(
    task_id: UUID,
    payload: WorkTaskUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> WorkTaskRead:
    return WorkforceService(db).update_task(task_id, current_user.id, payload)


@router.delete("/work-tasks/{task_id}", status_code=204)
def delete_work_task(task_id: UUID, current_user: CurrentUser, db: DBSession) -> None:
    WorkforceService(db).delete_task(task_id, current_user.id)


@router.get("/workforce/dashboard", response_model=WorkforceDashboard)
def workforce_dashboard(
    current_user: CurrentUser,
    db: DBSession,
    parcel_id: UUID | None = None,
    worker_id: UUID | None = None,
    task_type_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> WorkforceDashboard:
    return WorkforceService(db).dashboard(
        current_user.id,
        parcel_id=parcel_id,
        worker_id=worker_id,
        task_type_id=task_type_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/parcels/{parcel_id}/labor", response_model=ParcelLaborSummary)
def parcel_labor(parcel_id: UUID, current_user: CurrentUser, db: DBSession) -> ParcelLaborSummary:
    return WorkforceService(db).parcel_labor(parcel_id, current_user.id)
