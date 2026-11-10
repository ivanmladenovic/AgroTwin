"""Centralized Enterprise authorization helpers.

Producer operational mutations remain owner-scoped on existing endpoints.
Enterprise read access requires an active membership plus an explicit
active parcel assignment (supplier link alone is not enough).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enterprise import (
    EnterpriseMembership,
    EnterpriseOrganization,
    EnterpriseParcelAssignment,
    EnterpriseSupplierLink,
)
from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseOrgStatus,
    EnterpriseRelationshipStatus,
)
from app.models.parcel import Parcel
from app.models.user import User

ADMIN_ROLES = {EnterpriseMembershipRole.ENTERPRISE_ADMIN}
WRITE_PLAN_ROLES = {
    EnterpriseMembershipRole.ENTERPRISE_ADMIN,
    EnterpriseMembershipRole.ENTERPRISE_ANALYST,
}
ALL_ACTIVE_ROLES = {
    EnterpriseMembershipRole.ENTERPRISE_ADMIN,
    EnterpriseMembershipRole.ENTERPRISE_ANALYST,
    EnterpriseMembershipRole.ENTERPRISE_VIEWER,
}


class EnterpriseAccess:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_memberships(self, user_id: UUID) -> list[EnterpriseMembership]:
        stmt = (
            select(EnterpriseMembership)
            .join(EnterpriseOrganization)
            .where(
                EnterpriseMembership.user_id == user_id,
                EnterpriseMembership.status == EnterpriseMembershipStatus.ACTIVE,
                EnterpriseOrganization.status == EnterpriseOrgStatus.ACTIVE,
            )
            .order_by(EnterpriseOrganization.name.asc())
        )
        return list(self.db.scalars(stmt).all())

    def require_password_changed(self, user: User) -> None:
        """Block Enterprise data while a temporary password is still in force."""
        if user.must_change_password:
            raise ForbiddenError(
                "Morate promeniti privremenu lozinku pre pristupa Enterprise podacima"
            )

    def get_membership(
        self,
        user: User,
        organization_id: UUID,
        *,
        roles: set[EnterpriseMembershipRole] | None = None,
    ) -> EnterpriseMembership:
        self.require_password_changed(user)
        stmt = (
            select(EnterpriseMembership)
            .join(EnterpriseOrganization)
            .where(
                EnterpriseMembership.user_id == user.id,
                EnterpriseMembership.organization_id == organization_id,
                EnterpriseMembership.status == EnterpriseMembershipStatus.ACTIVE,
                EnterpriseOrganization.status == EnterpriseOrgStatus.ACTIVE,
            )
        )
        membership = self.db.scalars(stmt).first()
        if membership is None:
            raise ForbiddenError("Nemate pristup ovoj Enterprise organizaciji")
        allowed = roles or ALL_ACTIVE_ROLES
        if membership.role not in allowed:
            raise ForbiddenError("Nedovoljna Enterprise dozvola za ovu akciju")
        return membership

    def require_org(self, organization_id: UUID) -> EnterpriseOrganization:
        org = self.db.get(EnterpriseOrganization, organization_id)
        if org is None or org.status != EnterpriseOrgStatus.ACTIVE:
            raise NotFoundError("Enterprise organizacija nije pronađena")
        return org

    def require_admin(self, user: User, organization_id: UUID) -> EnterpriseMembership:
        return self.get_membership(user, organization_id, roles=ADMIN_ROLES)

    def require_plan_writer(self, user: User, organization_id: UUID) -> EnterpriseMembership:
        return self.get_membership(user, organization_id, roles=WRITE_PLAN_ROLES)

    def require_reader(self, user: User, organization_id: UUID) -> EnterpriseMembership:
        return self.get_membership(user, organization_id, roles=ALL_ACTIVE_ROLES)

    def active_assignment_filter(
        self,
        organization_id: UUID,
        *,
        on_date: date | None = None,
    ):
        today = on_date or date.today()
        return and_(
            EnterpriseParcelAssignment.organization_id == organization_id,
            EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE,
            or_(
                EnterpriseParcelAssignment.valid_from.is_(None),
                EnterpriseParcelAssignment.valid_from <= today,
            ),
            or_(
                EnterpriseParcelAssignment.valid_until.is_(None),
                EnterpriseParcelAssignment.valid_until >= today,
            ),
        )

    def assigned_parcel_ids(self, organization_id: UUID) -> set[UUID]:
        stmt = select(EnterpriseParcelAssignment.parcel_id).where(
            self.active_assignment_filter(organization_id)
        )
        return set(self.db.scalars(stmt).all())

    def assigned_farm_ids(self, organization_id: UUID) -> set[UUID]:
        stmt = select(EnterpriseParcelAssignment.farm_id).where(
            self.active_assignment_filter(organization_id)
        ).distinct()
        return set(self.db.scalars(stmt).all())

    def readable_parcel_ids(self, organization_id: UUID) -> set[UUID]:
        """Assigned parcels whose supplier link is still active and in the validity window."""
        today = date.today()
        stmt = (
            select(EnterpriseParcelAssignment.parcel_id)
            .join(
                EnterpriseSupplierLink,
                and_(
                    EnterpriseSupplierLink.organization_id == organization_id,
                    EnterpriseSupplierLink.farm_id == EnterpriseParcelAssignment.farm_id,
                    EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE,
                ),
            )
            .where(self.active_assignment_filter(organization_id, on_date=today))
        )
        return set(self.db.scalars(stmt).all())

    def user_can_read_parcel(self, user: User, parcel_id: UUID) -> bool:
        if user.must_change_password and self.list_memberships(user.id):
            raise ForbiddenError(
                "Morate promeniti privremenu lozinku pre pristupa Enterprise podacima"
            )
        for membership in self.list_memberships(user.id):
            if parcel_id in self.readable_parcel_ids(membership.organization_id):
                return True
        return False

    def require_parcel_read(self, organization_id: UUID, parcel_id: UUID) -> EnterpriseParcelAssignment:
        stmt = select(EnterpriseParcelAssignment).where(
            self.active_assignment_filter(organization_id),
            EnterpriseParcelAssignment.parcel_id == parcel_id,
        )
        assignment = self.db.scalars(stmt).first()
        if assignment is None:
            raise ForbiddenError("Parcela nije dodeljena ovoj Enterprise organizaciji")
        return assignment

    def require_supplier_link(self, organization_id: UUID, farm_id: UUID) -> EnterpriseSupplierLink:
        stmt = select(EnterpriseSupplierLink).where(
            EnterpriseSupplierLink.organization_id == organization_id,
            EnterpriseSupplierLink.farm_id == farm_id,
            EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE,
        )
        link = self.db.scalars(stmt).first()
        if link is None:
            raise ForbiddenError("Dobavljač nije aktivan u ovoj Enterprise organizaciji")
        return link

    def parcels_query(self, organization_id: UUID) -> Select[tuple[Parcel]]:
        return (
            select(Parcel)
            .join(
                EnterpriseParcelAssignment,
                EnterpriseParcelAssignment.parcel_id == Parcel.id,
            )
            .where(self.active_assignment_filter(organization_id))
        )

    def deny_producer_write(self) -> None:
        """Explicit guard for any future shared write path."""
        raise ForbiddenError(
            "Enterprise nalog ima samo pregled proizvođačkih operativnih podataka"
        )
