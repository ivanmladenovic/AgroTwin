"""Internal company tasks. They do not write the producer journal or alert status."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.enterprise.access import EnterpriseAccess
from app.models.enterprise import EnterpriseFollowUp, EnterpriseMembership
from app.models.enums import EnterpriseAuditAction, EnterpriseMembershipStatus
from app.models.farm import Farm
from app.models.intelligence import ParcelAlert
from app.models.parcel import Parcel
from app.models.user import User
from app.repositories.enterprise import EnterpriseRepository
from app.schemas.enterprise import (
    FOLLOW_UP_STATUSES,
    EnterpriseFollowUpCreate,
    EnterpriseFollowUpRead,
    EnterpriseFollowUpUpdate,
)

UPCOMING_DAYS = 7
_CLOSED = {"completed", "cancelled"}


class EnterpriseFollowUpService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.access = EnterpriseAccess(db)
        self.repo = EnterpriseRepository(db)

    def list_tasks(
        self,
        user: User,
        organization_id: UUID,
        *,
        status: str | None = None,
        farm_id: UUID | None = None,
        parcel_id: UUID | None = None,
        assignee_user_id: UUID | None = None,
        due: str | None = None,
        upcoming_days: int = UPCOMING_DAYS,
    ) -> list[EnterpriseFollowUpRead]:
        self.access.require_reader(user, organization_id)
        stmt = select(EnterpriseFollowUp).where(
            EnterpriseFollowUp.organization_id == organization_id
        )
        if status:
            self._status(status)
            stmt = stmt.where(EnterpriseFollowUp.status == status)
        if farm_id is not None:
            stmt = stmt.where(EnterpriseFollowUp.farm_id == farm_id)
        if parcel_id is not None:
            stmt = stmt.where(EnterpriseFollowUp.parcel_id == parcel_id)
        if assignee_user_id is not None:
            stmt = stmt.where(EnterpriseFollowUp.assignee_user_id == assignee_user_id)
        rows = list(self.db.scalars(stmt.order_by(EnterpriseFollowUp.created_at.desc())).all())
        today = date.today()
        window = max(1, min(upcoming_days, 30))
        if due == "overdue":
            rows = [
                item
                for item in rows
                if item.due_on is not None
                and item.due_on < today
                and item.status not in _CLOSED
            ]
        elif due == "upcoming":
            until = today + timedelta(days=window)
            rows = [
                item
                for item in rows
                if item.due_on is not None
                and today <= item.due_on <= until
                and item.status not in _CLOSED
            ]
        return [self._read(item) for item in rows]

    def create_task(
        self, user: User, organization_id: UUID, payload: EnterpriseFollowUpCreate
    ) -> EnterpriseFollowUpRead:
        self.access.require_plan_writer(user, organization_id)
        status = self._status(payload.status)
        farm_id, parcel_id, alert_id = self._links(
            organization_id,
            farm_id=payload.farm_id,
            parcel_id=payload.parcel_id,
            alert_id=payload.alert_id,
        )
        assignee_id = self._assignee(organization_id, payload.assignee_user_id)
        task = EnterpriseFollowUp(
            organization_id=organization_id,
            farm_id=farm_id,
            parcel_id=parcel_id,
            alert_id=alert_id,
            assignee_user_id=assignee_id,
            title=payload.title.strip(),
            body=(payload.body or "").strip() or None,
            status=status,
            due_on=payload.due_on,
            created_by_id=user.id,
        )
        self.db.add(task)
        self.db.flush()
        self.repo.record_audit(
            organization_id=organization_id,
            actor_user_id=user.id,
            action=EnterpriseAuditAction.FOLLOW_UP_CREATED.value,
            entity_type="follow_up",
            entity_id=task.id,
            details={"status": status},
        )
        self.db.flush()
        return self._read(task)

    def update_task(
        self,
        user: User,
        organization_id: UUID,
        task_id: UUID,
        payload: EnterpriseFollowUpUpdate,
    ) -> EnterpriseFollowUpRead:
        self.access.require_plan_writer(user, organization_id)
        task = self._get(organization_id, task_id)
        data = payload.model_dump(exclude_unset=True)
        previous_status = task.status
        if "status" in data and data["status"] is not None:
            data["status"] = self._status(data["status"])
        farm_id = data["farm_id"] if "farm_id" in data else task.farm_id
        parcel_id = data["parcel_id"] if "parcel_id" in data else task.parcel_id
        alert_id = data["alert_id"] if "alert_id" in data else task.alert_id
        if any(key in data for key in ("farm_id", "parcel_id", "alert_id")):
            farm_id, parcel_id, alert_id = self._links(
                organization_id, farm_id=farm_id, parcel_id=parcel_id, alert_id=alert_id
            )
            task.farm_id = farm_id
            task.parcel_id = parcel_id
            task.alert_id = alert_id
        if "assignee_user_id" in data:
            task.assignee_user_id = self._assignee(organization_id, data["assignee_user_id"])
        if "title" in data and data["title"] is not None:
            task.title = data["title"].strip()
        if "body" in data:
            task.body = (data["body"] or "").strip() or None
        if "due_on" in data:
            task.due_on = data["due_on"]
        if "status" in data and data["status"] is not None:
            task.status = data["status"]
        self.db.flush()
        changed = sorted(key for key in data if key != "status")
        if changed:
            self.repo.record_audit(
                organization_id=organization_id,
                actor_user_id=user.id,
                action=EnterpriseAuditAction.FOLLOW_UP_UPDATED.value,
                entity_type="follow_up",
                entity_id=task.id,
                details={"fields": changed},
            )
        if task.status != previous_status:
            self.repo.record_audit(
                organization_id=organization_id,
                actor_user_id=user.id,
                action=EnterpriseAuditAction.FOLLOW_UP_STATUS_CHANGED.value,
                entity_type="follow_up",
                entity_id=task.id,
                details={"from": previous_status, "to": task.status},
            )
        self.db.flush()
        return self._read(task)

    def _get(self, organization_id: UUID, task_id: UUID) -> EnterpriseFollowUp:
        task = self.db.get(EnterpriseFollowUp, task_id)
        if task is None or task.organization_id != organization_id:
            raise NotFoundError("Zadatak nije pronađen")
        return task

    def _status(self, value: str) -> str:
        if value not in FOLLOW_UP_STATUSES:
            raise ForbiddenError("Status zadatka nije podržan")
        return value

    def _assignee(self, organization_id: UUID, user_id: UUID | None) -> UUID | None:
        if user_id is None:
            return None
        membership = self.db.scalars(
            select(EnterpriseMembership).where(
                EnterpriseMembership.organization_id == organization_id,
                EnterpriseMembership.user_id == user_id,
                EnterpriseMembership.status == EnterpriseMembershipStatus.ACTIVE,
            )
        ).first()
        if membership is None:
            raise ForbiddenError("Odgovorno lice nije aktivan član ove organizacije")
        return user_id

    def _links(
        self,
        organization_id: UUID,
        *,
        farm_id: UUID | None,
        parcel_id: UUID | None,
        alert_id: UUID | None,
    ) -> tuple[UUID | None, UUID | None, UUID | None]:
        readable = self.access.readable_parcel_ids(organization_id)
        parcel = self.db.get(Parcel, parcel_id) if parcel_id else None
        if parcel_id is not None:
            if parcel is None or parcel.id not in readable:
                raise ForbiddenError("Parcela nije dodeljena ovoj organizaciji")
            if farm_id is not None and parcel.farm_id != farm_id:
                raise ForbiddenError("Parcela ne pripada izabranom dobavljaču")
            farm_id = parcel.farm_id
        if farm_id is not None:
            self.access.require_supplier_link(organization_id, farm_id)
        if alert_id is not None:
            alert = self.db.get(ParcelAlert, alert_id)
            if alert is None or alert.parcel_id not in readable:
                raise ForbiddenError("Alert nije na parceli koju ova organizacija sme da vidi")
            if parcel_id is not None and alert.parcel_id != parcel_id:
                raise ForbiddenError("Alert ne pripada izabranoj parceli")
            if parcel is None:
                parcel = self.db.get(Parcel, alert.parcel_id)
                parcel_id = alert.parcel_id
                if parcel is not None:
                    farm_id = parcel.farm_id
        return farm_id, parcel_id, alert_id

    def _read(self, task: EnterpriseFollowUp) -> EnterpriseFollowUpRead:
        farm = self.db.get(Farm, task.farm_id) if task.farm_id else None
        parcel = self.db.get(Parcel, task.parcel_id) if task.parcel_id else None
        assignee = self.db.get(User, task.assignee_user_id) if task.assignee_user_id else None
        return EnterpriseFollowUpRead(
            id=task.id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            organization_id=task.organization_id,
            farm_id=task.farm_id,
            parcel_id=task.parcel_id,
            alert_id=task.alert_id,
            assignee_user_id=task.assignee_user_id,
            title=task.title,
            body=task.body,
            status=task.status,
            due_on=task.due_on,
            created_by_id=task.created_by_id,
            farm_name=farm.name if farm else None,
            parcel_name=parcel.name if parcel else None,
            assignee_name=assignee.full_name if assignee else None,
        )
