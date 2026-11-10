from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import WorkTaskStatus, pg_enum

if TYPE_CHECKING:
    from app.models.cost import Cost
    from app.models.farm import Farm
    from app.models.parcel import Parcel


class WorkTaskType(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Configurable catalog of workforce task types (seeded, not UI-hardcoded)."""

    __tablename__ = "work_task_types"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tasks: Mapped[list[WorkTask]] = relationship("WorkTask", back_populates="task_type")


class Worker(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workers"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    farm: Mapped[Farm] = relationship("Farm")
    tasks: Mapped[list[WorkTask]] = relationship("WorkTask", back_populates="worker")


class WorkTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_tasks"

    farm_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("work_task_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    worked_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    hourly_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[WorkTaskStatus] = mapped_column(
        pg_enum(WorkTaskStatus, "work_task_status"),
        nullable=False,
        default=WorkTaskStatus.COMPLETED,
        index=True,
    )
    cost_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("costs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    farm: Mapped[Farm] = relationship("Farm")
    parcel: Mapped[Parcel] = relationship("Parcel")
    worker: Mapped[Worker] = relationship("Worker", back_populates="tasks")
    task_type: Mapped[WorkTaskType] = relationship("WorkTaskType", back_populates="tasks")
    cost: Mapped[Cost | None] = relationship("Cost", foreign_keys=[cost_id])
