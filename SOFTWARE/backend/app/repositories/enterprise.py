from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enterprise import (
    EnterpriseAuditEvent,
    EnterpriseMembership,
    EnterpriseOrganization,
    EnterpriseParcelAssignment,
    EnterprisePlanningSeason,
    EnterpriseSupplierLink,
    EnterpriseYieldPlan,
    EnterpriseYieldPlanItem,
)
from app.models.enums import EnterpriseAssignmentStatus, EnterpriseMembershipStatus
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.tree import Tree
from app.models.enums import TreeStatus


class EnterpriseRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, entity):
        self.db.add(entity)
        return entity

    def get_org_by_slug(self, slug: str) -> EnterpriseOrganization | None:
        return self.db.scalars(
            select(EnterpriseOrganization).where(EnterpriseOrganization.slug == slug)
        ).first()

    def get_org(self, organization_id: UUID) -> EnterpriseOrganization | None:
        return self.db.get(EnterpriseOrganization, organization_id)

    def list_memberships_for_user(self, user_id: UUID) -> list[EnterpriseMembership]:
        stmt = (
            select(EnterpriseMembership)
            .options(selectinload(EnterpriseMembership.organization))
            .where(
                EnterpriseMembership.user_id == user_id,
                EnterpriseMembership.status == EnterpriseMembershipStatus.ACTIVE,
            )
            .order_by(EnterpriseMembership.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_membership(self, organization_id: UUID, user_id: UUID) -> EnterpriseMembership | None:
        return self.db.scalars(
            select(EnterpriseMembership).where(
                EnterpriseMembership.organization_id == organization_id,
                EnterpriseMembership.user_id == user_id,
            )
        ).first()

    def list_supplier_links(self, organization_id: UUID) -> list[EnterpriseSupplierLink]:
        stmt = (
            select(EnterpriseSupplierLink)
            .options(selectinload(EnterpriseSupplierLink.farm))
            .where(EnterpriseSupplierLink.organization_id == organization_id)
            .order_by(EnterpriseSupplierLink.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_supplier_link(
        self, organization_id: UUID, link_id: UUID
    ) -> EnterpriseSupplierLink | None:
        return self.db.scalars(
            select(EnterpriseSupplierLink)
            .options(selectinload(EnterpriseSupplierLink.farm))
            .where(
                EnterpriseSupplierLink.id == link_id,
                EnterpriseSupplierLink.organization_id == organization_id,
            )
        ).first()

    def get_supplier_by_farm(
        self, organization_id: UUID, farm_id: UUID
    ) -> EnterpriseSupplierLink | None:
        return self.db.scalars(
            select(EnterpriseSupplierLink)
            .options(selectinload(EnterpriseSupplierLink.farm))
            .where(
                EnterpriseSupplierLink.organization_id == organization_id,
                EnterpriseSupplierLink.farm_id == farm_id,
            )
        ).first()

    def list_parcel_assignments(self, organization_id: UUID) -> list[EnterpriseParcelAssignment]:
        stmt = (
            select(EnterpriseParcelAssignment)
            .options(
                selectinload(EnterpriseParcelAssignment.parcel),
                selectinload(EnterpriseParcelAssignment.farm),
            )
            .where(EnterpriseParcelAssignment.organization_id == organization_id)
            .order_by(EnterpriseParcelAssignment.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_parcel_assignment(
        self, organization_id: UUID, assignment_id: UUID
    ) -> EnterpriseParcelAssignment | None:
        return self.db.scalars(
            select(EnterpriseParcelAssignment)
            .options(
                selectinload(EnterpriseParcelAssignment.parcel),
                selectinload(EnterpriseParcelAssignment.farm),
            )
            .where(
                EnterpriseParcelAssignment.id == assignment_id,
                EnterpriseParcelAssignment.organization_id == organization_id,
            )
        ).first()

    def get_assignment_by_parcel(
        self, organization_id: UUID, parcel_id: UUID
    ) -> EnterpriseParcelAssignment | None:
        return self.db.scalars(
            select(EnterpriseParcelAssignment).where(
                EnterpriseParcelAssignment.organization_id == organization_id,
                EnterpriseParcelAssignment.parcel_id == parcel_id,
            )
        ).first()

    def count_active_assignments_for_farm(self, organization_id: UUID, farm_id: UUID) -> int:
        stmt = select(func.count()).select_from(EnterpriseParcelAssignment).where(
            EnterpriseParcelAssignment.organization_id == organization_id,
            EnterpriseParcelAssignment.farm_id == farm_id,
            EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE,
        )
        return int(self.db.scalar(stmt) or 0)

    def sum_assigned_area_for_farm(self, organization_id: UUID, farm_id: UUID):
        stmt = (
            select(func.coalesce(func.sum(Parcel.area_hectares), 0))
            .select_from(EnterpriseParcelAssignment)
            .join(Parcel, Parcel.id == EnterpriseParcelAssignment.parcel_id)
            .where(
                EnterpriseParcelAssignment.organization_id == organization_id,
                EnterpriseParcelAssignment.farm_id == farm_id,
                EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE,
            )
        )
        return self.db.scalar(stmt)

    def list_seasons(self, organization_id: UUID) -> list[EnterprisePlanningSeason]:
        stmt = (
            select(EnterprisePlanningSeason)
            .where(EnterprisePlanningSeason.organization_id == organization_id)
            .order_by(EnterprisePlanningSeason.year.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_season(self, organization_id: UUID, season_id: UUID) -> EnterprisePlanningSeason | None:
        return self.db.scalars(
            select(EnterprisePlanningSeason).where(
                EnterprisePlanningSeason.id == season_id,
                EnterprisePlanningSeason.organization_id == organization_id,
            )
        ).first()

    def get_season_by_year(
        self, organization_id: UUID, year: int
    ) -> EnterprisePlanningSeason | None:
        return self.db.scalars(
            select(EnterprisePlanningSeason).where(
                EnterprisePlanningSeason.organization_id == organization_id,
                EnterprisePlanningSeason.year == year,
            )
        ).first()

    def list_yield_plans(
        self, organization_id: UUID, season_id: UUID | None = None
    ) -> list[EnterpriseYieldPlan]:
        stmt = (
            select(EnterpriseYieldPlan)
            .options(selectinload(EnterpriseYieldPlan.items))
            .where(EnterpriseYieldPlan.organization_id == organization_id)
        )
        if season_id is not None:
            stmt = stmt.where(EnterpriseYieldPlan.planning_season_id == season_id)
        stmt = stmt.order_by(EnterpriseYieldPlan.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def get_yield_plan(self, organization_id: UUID, plan_id: UUID) -> EnterpriseYieldPlan | None:
        return self.db.scalars(
            select(EnterpriseYieldPlan)
            .options(selectinload(EnterpriseYieldPlan.items))
            .where(
                EnterpriseYieldPlan.id == plan_id,
                EnterpriseYieldPlan.organization_id == organization_id,
            )
        ).first()

    def tree_count(self, parcel_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Tree)
            .where(Tree.parcel_id == parcel_id, Tree.status == TreeStatus.ACTIVE)
        )
        return int(self.db.scalar(stmt) or 0)

    def get_parcel(self, parcel_id: UUID) -> Parcel | None:
        return self.db.scalars(
            select(Parcel).options(selectinload(Parcel.farm)).where(Parcel.id == parcel_id)
        ).first()

    def get_farm(self, farm_id: UUID) -> Farm | None:
        return self.db.get(Farm, farm_id)

    def record_audit(
        self,
        *,
        organization_id: UUID,
        actor_user_id: UUID | None,
        action: str,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        details: dict | None = None,
    ) -> EnterpriseAuditEvent:
        event = EnterpriseAuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
        self.db.add(event)
        return event
