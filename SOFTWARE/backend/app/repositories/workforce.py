from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.farm import Farm
from app.models.enums import WorkTaskStatus
from app.models.workforce import WorkTask, WorkTaskType, Worker


class WorkforceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_task_types(self, *, active_only: bool = True) -> list[WorkTaskType]:
        stmt = select(WorkTaskType).order_by(WorkTaskType.sort_order, WorkTaskType.name)
        if active_only:
            stmt = stmt.where(WorkTaskType.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get_task_type(self, type_id: UUID) -> WorkTaskType | None:
        return self.db.get(WorkTaskType, type_id)

    def get_task_type_by_slug(self, slug: str) -> WorkTaskType | None:
        stmt = select(WorkTaskType).where(WorkTaskType.slug == slug)
        return self.db.scalars(stmt).first()

    def _workers_owned(self, owner_id: UUID) -> Select[tuple[Worker]]:
        return (
            select(Worker)
            .join(Farm, Worker.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )

    def list_workers(
        self,
        owner_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[Worker]:
        stmt = self._workers_owned(owner_id).order_by(Worker.last_name, Worker.first_name)
        if active_only:
            stmt = stmt.where(Worker.active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get_worker_for_owner(self, worker_id: UUID, owner_id: UUID) -> Worker | None:
        stmt = self._workers_owned(owner_id).where(Worker.id == worker_id)
        return self.db.scalars(stmt).first()

    def count_workers(self, owner_id: UUID, *, active_only: bool = True) -> int:
        stmt = (
            select(func.count())
            .select_from(Worker)
            .join(Farm, Worker.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
        )
        if active_only:
            stmt = stmt.where(Worker.active.is_(True))
        return int(self.db.scalar(stmt) or 0)

    def add_worker(self, worker: Worker) -> Worker:
        self.db.add(worker)
        return worker

    def _tasks_owned(self, owner_id: UUID) -> Select[tuple[WorkTask]]:
        return (
            select(WorkTask)
            .join(Farm, WorkTask.farm_id == Farm.id)
            .where(Farm.owner_id == owner_id)
            .options(
                selectinload(WorkTask.worker),
                selectinload(WorkTask.task_type),
                selectinload(WorkTask.parcel),
            )
        )

    def list_tasks(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        worker_id: UUID | None = None,
        task_type_id: UUID | None = None,
        status: WorkTaskStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int | None = None,
    ) -> list[WorkTask]:
        stmt = self._tasks_owned(owner_id)
        if parcel_id is not None:
            stmt = stmt.where(WorkTask.parcel_id == parcel_id)
        if worker_id is not None:
            stmt = stmt.where(WorkTask.worker_id == worker_id)
        if task_type_id is not None:
            stmt = stmt.where(WorkTask.task_type_id == task_type_id)
        if status is not None:
            stmt = stmt.where(WorkTask.status == status)
        if date_from is not None:
            stmt = stmt.where(WorkTask.worked_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(WorkTask.worked_on <= date_to)
        stmt = stmt.order_by(WorkTask.worked_on.desc(), WorkTask.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt).unique().all())

    def get_task_for_owner(self, task_id: UUID, owner_id: UUID) -> WorkTask | None:
        stmt = self._tasks_owned(owner_id).where(WorkTask.id == task_id)
        return self.db.scalars(stmt).unique().first()

    def add_task(self, task: WorkTask) -> WorkTask:
        self.db.add(task)
        return task

    def aggregate_completed(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        worker_id: UUID | None = None,
        task_type_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[Decimal, Decimal, int]:
        stmt = (
            select(
                func.coalesce(func.sum(WorkTask.labor_cost), 0),
                func.coalesce(func.sum(WorkTask.hours), 0),
                func.count(WorkTask.id),
            )
            .join(Farm, WorkTask.farm_id == Farm.id)
            .where(
                Farm.owner_id == owner_id,
                WorkTask.status == WorkTaskStatus.COMPLETED,
            )
        )
        if parcel_id is not None:
            stmt = stmt.where(WorkTask.parcel_id == parcel_id)
        if worker_id is not None:
            stmt = stmt.where(WorkTask.worker_id == worker_id)
        if task_type_id is not None:
            stmt = stmt.where(WorkTask.task_type_id == task_type_id)
        if date_from is not None:
            stmt = stmt.where(WorkTask.worked_on >= date_from)
        if date_to is not None:
            stmt = stmt.where(WorkTask.worked_on <= date_to)
        row = self.db.execute(stmt).one()
        return Decimal(row[0] or 0), Decimal(row[1] or 0), int(row[2] or 0)
