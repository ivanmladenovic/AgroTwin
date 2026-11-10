from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.models.enums import WorkTaskStatus
from app.schemas.catalog import CatalogItemRead
from app.schemas.common import IDSchema, ORMModel


class WorkerCreate(ORMModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    hourly_rate: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    active: bool = True


class WorkerUpdate(ORMModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    hourly_rate: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    active: bool | None = None


class WorkerRead(IDSchema):
    farm_id: UUID
    first_name: str
    last_name: str
    hourly_rate: Decimal
    active: bool
    created_by_id: UUID | None = None


class WorkTaskCreate(ORMModel):
    worker_id: UUID
    parcel_id: UUID
    task_type_id: UUID
    description: str | None = None
    worked_on: date
    hours: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    hourly_rate: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    status: WorkTaskStatus = WorkTaskStatus.COMPLETED


class WorkTaskUpdate(ORMModel):
    worker_id: UUID | None = None
    parcel_id: UUID | None = None
    task_type_id: UUID | None = None
    description: str | None = None
    worked_on: date | None = None
    hours: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    hourly_rate: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    status: WorkTaskStatus | None = None


class WorkTaskRead(IDSchema):
    farm_id: UUID
    parcel_id: UUID
    worker_id: UUID
    task_type_id: UUID
    description: str | None
    worked_on: date
    hours: Decimal
    hourly_rate_snapshot: Decimal
    labor_cost: Decimal
    status: WorkTaskStatus
    cost_id: UUID | None
    created_by_id: UUID | None = None
    worker_name: str | None = None
    parcel_name: str | None = None
    task_type: CatalogItemRead | None = None


class WorkforceBreakdownItem(ORMModel):
    id: UUID | None = None
    label: str
    hours: Decimal
    labor_cost: Decimal
    task_count: int = 0


class WorkforceDashboard(ORMModel):
    total_labor_cost: Decimal
    total_hours: Decimal
    worker_count: int
    task_count: int
    by_worker: list[WorkforceBreakdownItem]
    by_task_type: list[WorkforceBreakdownItem]
    by_parcel: list[WorkforceBreakdownItem]


class ParcelLaborSummary(ORMModel):
    parcel_id: UUID
    total_hours: Decimal
    total_labor_cost: Decimal
    recent_tasks: list[WorkTaskRead]


def compute_labor_cost(hours: Decimal, hourly_rate: Decimal) -> Decimal:
    return (hours * hourly_rate).quantize(Decimal("0.01"))
