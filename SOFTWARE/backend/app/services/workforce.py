from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.models.cost import Cost
from app.models.enums import CostSource, ScopeType, WorkTaskStatus
from app.models.workforce import WorkTask, Worker
from app.repositories.catalog import CatalogRepository
from app.repositories.cost import CostRepository
from app.repositories.farm import FarmRepository
from app.repositories.parcel import ParcelRepository
from app.repositories.workforce import WorkforceRepository
from app.schemas.catalog import CatalogItemRead
from app.schemas.workforce import (
    ParcelLaborSummary,
    WorkTaskCreate,
    WorkTaskRead,
    WorkTaskUpdate,
    WorkerCreate,
    WorkerRead,
    WorkerUpdate,
    WorkforceBreakdownItem,
    WorkforceDashboard,
    compute_labor_cost,
)


class WorkforceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workforce = WorkforceRepository(db)
        self.farms = FarmRepository(db)
        self.parcels = ParcelRepository(db)
        self.catalogs = CatalogRepository(db)
        self.costs = CostRepository(db)

    # --- Workers -----------------------------------------------------------------

    def list_workers(self, owner_id: UUID, *, active_only: bool = False) -> list[WorkerRead]:
        return [self.to_worker_read(w) for w in self.workforce.list_workers(owner_id, active_only=active_only)]

    def create_worker(self, owner_id: UUID, payload: WorkerCreate, created_by_id: UUID) -> WorkerRead:
        farm = self._farm(owner_id)
        worker = Worker(
            farm_id=farm.id,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            hourly_rate=payload.hourly_rate.quantize(Decimal("0.01")),
            active=payload.active,
            created_by_id=created_by_id,
        )
        self.workforce.add_worker(worker)
        self.db.commit()
        self.db.refresh(worker)
        return self.to_worker_read(worker)

    def update_worker(self, worker_id: UUID, owner_id: UUID, payload: WorkerUpdate) -> WorkerRead:
        worker = self._get_worker(worker_id, owner_id)
        data = payload.model_dump(exclude_unset=True)
        if "first_name" in data and data["first_name"] is not None:
            worker.first_name = data["first_name"].strip()
        if "last_name" in data and data["last_name"] is not None:
            worker.last_name = data["last_name"].strip()
        if "hourly_rate" in data and data["hourly_rate"] is not None:
            worker.hourly_rate = data["hourly_rate"].quantize(Decimal("0.01"))
        if "active" in data and data["active"] is not None:
            worker.active = data["active"]
        self.db.commit()
        self.db.refresh(worker)
        return self.to_worker_read(worker)

    def delete_worker(self, worker_id: UUID, owner_id: UUID) -> None:
        worker = self._get_worker(worker_id, owner_id)
        tasks = self.workforce.list_tasks(owner_id, worker_id=worker.id, limit=1)
        if tasks:
            raise AppError(
                "Radnik ima evidentirane zadatke i ne može se obrisati. Deaktivirajte ga umesto toga.",
                status_code=422,
                code="worker_has_tasks",
            )
        self.db.delete(worker)
        self.db.commit()

    # --- Task types --------------------------------------------------------------

    def list_task_types(self) -> list[CatalogItemRead]:
        return [CatalogItemRead.model_validate(item) for item in self.workforce.list_task_types()]

    # --- Work tasks --------------------------------------------------------------

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
    ) -> list[WorkTaskRead]:
        if parcel_id is not None and self.parcels.get_for_owner(parcel_id, owner_id) is None:
            raise NotFoundError("Parcela nije pronađena")
        if worker_id is not None and self.workforce.get_worker_for_owner(worker_id, owner_id) is None:
            raise NotFoundError("Radnik nije pronađen")
        tasks = self.workforce.list_tasks(
            owner_id,
            parcel_id=parcel_id,
            worker_id=worker_id,
            task_type_id=task_type_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
        return [self.to_task_read(task) for task in tasks]

    def get_task(self, task_id: UUID, owner_id: UUID) -> WorkTaskRead:
        return self.to_task_read(self._get_task(task_id, owner_id))

    def create_task(self, owner_id: UUID, payload: WorkTaskCreate, created_by_id: UUID) -> WorkTaskRead:
        farm = self._farm(owner_id)
        worker = self._get_worker(payload.worker_id, owner_id)
        parcel = self.parcels.get_for_owner(payload.parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        if parcel.farm_id != farm.id:
            raise AppError("Parcela ne pripada gazdinstvu.", status_code=422, code="parcel_farm_mismatch")
        task_type = self.workforce.get_task_type(payload.task_type_id)
        if task_type is None or not task_type.is_active:
            raise NotFoundError("Tip zadatka nije pronađen")

        rate = (
            payload.hourly_rate.quantize(Decimal("0.01"))
            if payload.hourly_rate is not None
            else worker.hourly_rate.quantize(Decimal("0.01"))
        )
        hours = payload.hours.quantize(Decimal("0.01"))
        labor_cost = compute_labor_cost(hours, rate)

        task = WorkTask(
            farm_id=farm.id,
            parcel_id=parcel.id,
            worker_id=worker.id,
            task_type_id=task_type.id,
            description=(payload.description or "").strip() or None,
            worked_on=payload.worked_on,
            hours=hours,
            hourly_rate_snapshot=rate,
            labor_cost=labor_cost,
            status=payload.status,
            created_by_id=created_by_id,
        )
        self.workforce.add_task(task)
        self.db.flush()
        self._sync_cost(task, owner_id=owner_id, created_by_id=created_by_id)
        self.db.commit()
        loaded = self.workforce.get_task_for_owner(task.id, owner_id)
        if loaded is None:
            raise NotFoundError("Zadatak nije pronađen")
        return self.to_task_read(loaded)

    def update_task(self, task_id: UUID, owner_id: UUID, payload: WorkTaskUpdate) -> WorkTaskRead:
        task = self._get_task(task_id, owner_id)
        data = payload.model_dump(exclude_unset=True)

        if "worker_id" in data and data["worker_id"] is not None:
            worker = self._get_worker(data["worker_id"], owner_id)
            task.worker_id = worker.id
        if "parcel_id" in data and data["parcel_id"] is not None:
            parcel = self.parcels.get_for_owner(data["parcel_id"], owner_id)
            if parcel is None:
                raise NotFoundError("Parcela nije pronađena")
            task.parcel_id = parcel.id
            task.farm_id = parcel.farm_id
        if "task_type_id" in data and data["task_type_id"] is not None:
            task_type = self.workforce.get_task_type(data["task_type_id"])
            if task_type is None or not task_type.is_active:
                raise NotFoundError("Tip zadatka nije pronađen")
            task.task_type_id = task_type.id
        if "description" in data:
            task.description = (data["description"] or "").strip() or None
        if "worked_on" in data and data["worked_on"] is not None:
            task.worked_on = data["worked_on"]
        if "hours" in data and data["hours"] is not None:
            task.hours = data["hours"].quantize(Decimal("0.01"))
        if "hourly_rate" in data and data["hourly_rate"] is not None:
            # Explicit rate edit updates the snapshot for this historical task only.
            task.hourly_rate_snapshot = data["hourly_rate"].quantize(Decimal("0.01"))
        if "status" in data and data["status"] is not None:
            task.status = data["status"]

        task.labor_cost = compute_labor_cost(task.hours, task.hourly_rate_snapshot)
        self._sync_cost(task, owner_id=owner_id, created_by_id=task.created_by_id or owner_id)
        self.db.commit()
        loaded = self.workforce.get_task_for_owner(task.id, owner_id)
        if loaded is None:
            raise NotFoundError("Zadatak nije pronađen")
        return self.to_task_read(loaded)

    def delete_task(self, task_id: UUID, owner_id: UUID) -> None:
        task = self._get_task(task_id, owner_id)
        self._remove_cost(task)
        self.db.delete(task)
        self.db.commit()

    # --- Dashboard / parcel ------------------------------------------------------

    def dashboard(
        self,
        owner_id: UUID,
        *,
        parcel_id: UUID | None = None,
        worker_id: UUID | None = None,
        task_type_id: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> WorkforceDashboard:
        total_cost, total_hours, task_count = self.workforce.aggregate_completed(
            owner_id,
            parcel_id=parcel_id,
            worker_id=worker_id,
            task_type_id=task_type_id,
            date_from=date_from,
            date_to=date_to,
        )
        tasks = self.workforce.list_tasks(
            owner_id,
            parcel_id=parcel_id,
            worker_id=worker_id,
            task_type_id=task_type_id,
            status=WorkTaskStatus.COMPLETED,
            date_from=date_from,
            date_to=date_to,
        )
        by_worker: dict[UUID, WorkforceBreakdownItem] = {}
        by_type: dict[UUID, WorkforceBreakdownItem] = {}
        by_parcel: dict[UUID, WorkforceBreakdownItem] = {}
        for task in tasks:
            worker_key = task.worker_id
            if worker_key not in by_worker:
                name = f"{task.worker.first_name} {task.worker.last_name}".strip() if task.worker else "Radnik"
                by_worker[worker_key] = WorkforceBreakdownItem(
                    id=worker_key, label=name, hours=Decimal("0"), labor_cost=Decimal("0"), task_count=0
                )
            by_worker[worker_key].hours += task.hours
            by_worker[worker_key].labor_cost += task.labor_cost
            by_worker[worker_key].task_count += 1

            type_key = task.task_type_id
            if type_key not in by_type:
                label = task.task_type.name if task.task_type else "Zadatak"
                by_type[type_key] = WorkforceBreakdownItem(
                    id=type_key, label=label, hours=Decimal("0"), labor_cost=Decimal("0"), task_count=0
                )
            by_type[type_key].hours += task.hours
            by_type[type_key].labor_cost += task.labor_cost
            by_type[type_key].task_count += 1

            parcel_key = task.parcel_id
            if parcel_key not in by_parcel:
                label = task.parcel.name if task.parcel else "Parcela"
                by_parcel[parcel_key] = WorkforceBreakdownItem(
                    id=parcel_key, label=label, hours=Decimal("0"), labor_cost=Decimal("0"), task_count=0
                )
            by_parcel[parcel_key].hours += task.hours
            by_parcel[parcel_key].labor_cost += task.labor_cost
            by_parcel[parcel_key].task_count += 1

        def _sorted(items: dict[UUID, WorkforceBreakdownItem]) -> list[WorkforceBreakdownItem]:
            return sorted(items.values(), key=lambda item: item.labor_cost, reverse=True)

        return WorkforceDashboard(
            total_labor_cost=total_cost.quantize(Decimal("0.01")),
            total_hours=total_hours.quantize(Decimal("0.01")),
            worker_count=self.workforce.count_workers(owner_id, active_only=True),
            task_count=task_count,
            by_worker=_sorted(by_worker),
            by_task_type=_sorted(by_type),
            by_parcel=_sorted(by_parcel),
        )

    def parcel_labor(self, parcel_id: UUID, owner_id: UUID, *, limit: int = 10) -> ParcelLaborSummary:
        parcel = self.parcels.get_for_owner(parcel_id, owner_id)
        if parcel is None:
            raise NotFoundError("Parcela nije pronađena")
        total_cost, total_hours, _ = self.workforce.aggregate_completed(owner_id, parcel_id=parcel_id)
        recent = self.workforce.list_tasks(
            owner_id,
            parcel_id=parcel_id,
            status=WorkTaskStatus.COMPLETED,
            limit=limit,
        )
        return ParcelLaborSummary(
            parcel_id=parcel_id,
            total_hours=total_hours.quantize(Decimal("0.01")),
            total_labor_cost=total_cost.quantize(Decimal("0.01")),
            recent_tasks=[self.to_task_read(task) for task in recent],
        )

    # --- Serialization -----------------------------------------------------------

    def to_worker_read(self, worker: Worker) -> WorkerRead:
        return WorkerRead.model_validate(worker)

    def to_task_read(self, task: WorkTask) -> WorkTaskRead:
        worker_name = None
        if task.worker is not None:
            worker_name = f"{task.worker.first_name} {task.worker.last_name}".strip()
        parcel_name = task.parcel.name if task.parcel is not None else None
        task_type = CatalogItemRead.model_validate(task.task_type) if task.task_type is not None else None
        return WorkTaskRead(
            id=task.id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            farm_id=task.farm_id,
            parcel_id=task.parcel_id,
            worker_id=task.worker_id,
            task_type_id=task.task_type_id,
            description=task.description,
            worked_on=task.worked_on,
            hours=task.hours,
            hourly_rate_snapshot=task.hourly_rate_snapshot,
            labor_cost=task.labor_cost,
            status=task.status,
            cost_id=task.cost_id,
            created_by_id=task.created_by_id,
            worker_name=worker_name,
            parcel_name=parcel_name,
            task_type=task_type,
        )

    # --- Cost sync ---------------------------------------------------------------

    def _sync_cost(self, task: WorkTask, *, owner_id: UUID, created_by_id: UUID) -> None:
        if task.status != WorkTaskStatus.COMPLETED:
            self._remove_cost(task)
            return

        category = self.catalogs.get_cost_category_by_slug("labor")
        if category is None:
            raise AppError("Kategorija troška 'labor' nije pronađena.", status_code=500, code="missing_labor_category")

        worker = task.worker or self.db.get(Worker, task.worker_id)
        worker_label = f"{worker.first_name} {worker.last_name}".strip() if worker else "Radnik"
        type_label = task.task_type.name if task.task_type else "Rad"
        description = f"Rad — {type_label} · {worker_label}"[:255]

        if task.cost_id is not None:
            cost = self.costs.get_for_owner(task.cost_id, owner_id)
            if cost is not None:
                cost.amount = task.labor_cost
                cost.incurred_on = task.worked_on
                cost.description = description
                cost.parcel_id = task.parcel_id
                cost.farm_id = task.farm_id
                cost.cost_category_id = category.id
                cost.source = CostSource.WORK_TASK
                cost.source_id = task.id
                return

        cost = Cost(
            amount=task.labor_cost,
            currency="EUR",
            incurred_on=task.worked_on,
            description=description,
            cost_category_id=category.id,
            activity_id=None,
            source=CostSource.WORK_TASK,
            source_id=task.id,
            notes=task.description,
            receipt_filename=None,
            created_by_id=created_by_id,
            scope_type=ScopeType.PARCEL,
            farm_id=task.farm_id,
            parcel_id=task.parcel_id,
            row_id=None,
            tree_id=None,
        )
        self.costs.add(cost)
        self.db.flush()
        task.cost_id = cost.id

    def _remove_cost(self, task: WorkTask) -> None:
        if task.cost_id is None:
            return
        cost = self.db.get(Cost, task.cost_id)
        task.cost_id = None
        self.db.flush()
        if cost is not None:
            self.db.delete(cost)

    # --- Helpers -----------------------------------------------------------------

    def _farm(self, owner_id: UUID):
        farms = self.farms.list_by_owner(owner_id)
        if not farms:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        return farms[0]

    def _get_worker(self, worker_id: UUID, owner_id: UUID) -> Worker:
        worker = self.workforce.get_worker_for_owner(worker_id, owner_id)
        if worker is None:
            raise NotFoundError("Radnik nije pronađen")
        return worker

    def _get_task(self, task_id: UUID, owner_id: UUID) -> WorkTask:
        task = self.workforce.get_task_for_owner(task_id, owner_id)
        if task is None:
            raise NotFoundError("Zadatak nije pronađen")
        return task
