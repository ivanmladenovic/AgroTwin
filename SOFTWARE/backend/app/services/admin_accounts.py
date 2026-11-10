"""Platform-admin account management (superuser only).

Client accounts own farms/parcels.
Enterprise orgs receive explicit read-only assignments to those farms/parcels.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_password
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
from app.models.farm import Farm
from app.models.parcel import Parcel
from app.models.user import User
from app.repositories.enterprise import EnterpriseRepository
from app.repositories.user import UserRepository
from app.schemas.admin_accounts import (
    AdminAccountsOverview,
    AdminAssignParcelsRequest,
    AdminClientCreate,
    AdminClientFarmDetail,
    AdminClientParcel,
    AdminEnterpriseOrgCreate,
    AdminEnterpriseOrgSummary,
    AdminEnterpriseUserCreate,
    AdminLinkFarmRequest,
    AdminParcelAssignmentDetail,
    AdminSupplierLinkDetail,
    AdminUserDeleteResult,
    AdminUserEnterpriseMembership,
    AdminUserFarmSummary,
    AdminUserSummary,
    AdminUserUpdate,
)
from app.services.enterprise import ensure_organization


class AdminAccountsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.enterprise = EnterpriseRepository(db)

    def overview(self) -> AdminAccountsOverview:
        users = list(self.db.scalars(select(User)).all())
        client = 0
        enterprise = 0
        admins = 0
        for user in users:
            kinds = self._account_kinds(user)
            if "platform_admin" in kinds:
                admins += 1
            if "client" in kinds:
                client += 1
            if "enterprise" in kinds:
                enterprise += 1
        org_count = int(self.db.scalar(select(func.count()).select_from(EnterpriseOrganization)) or 0)
        supplier_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(EnterpriseSupplierLink)
                .where(EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE)
            )
            or 0
        )
        assignment_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(EnterpriseParcelAssignment)
                .where(EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE)
            )
            or 0
        )
        return AdminAccountsOverview(
            total_users=len(users),
            client_users=client,
            enterprise_users=enterprise,
            platform_admins=admins,
            enterprise_organizations=org_count,
            active_supplier_links=supplier_count,
            active_parcel_assignments=assignment_count,
        )

    def list_users(self, *, q: str | None = None) -> list[AdminUserSummary]:
        users = list(self.db.scalars(select(User).order_by(User.created_at.desc())).all())
        results: list[AdminUserSummary] = []
        for user in users:
            if q:
                needle = q.lower()
                hay = f"{user.email} {user.full_name}".lower()
                if needle not in hay:
                    continue
            results.append(self._user_summary(user))
        return results

    def get_user(self, user_id: UUID) -> AdminUserSummary:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Korisnik nije pronađen")
        return self._user_summary(user)

    def create_client(self, payload: AdminClientCreate) -> AdminUserSummary:
        if self.users.get_by_email(payload.email.lower()):
            raise ForbiddenError("Korisnik sa ovom e-poštom već postoji")
        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            hashed_password=hash_password(payload.temporary_password),
            is_active=True,
            is_superuser=False,
            must_change_password=False,
        )
        self.users.add(user)
        self.db.flush()
        if payload.farm_name:
            farm = Farm(
                owner_id=user.id,
                name=payload.farm_name,
                location_name=payload.location_name,
            )
            self.db.add(farm)
            self.db.flush()
        return self._user_summary(user)

    def update_user(self, user_id: UUID, payload: AdminUserUpdate) -> AdminUserSummary:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Korisnik nije pronađen")
        data = payload.model_dump(exclude_unset=True)
        if "temporary_password" in data:
            password = data.pop("temporary_password")
            if password:
                user.hashed_password = hash_password(password)
                user.must_change_password = False
        if "email" in data and data["email"] is not None:
            email = str(data.pop("email")).lower().strip()
            existing = self.users.get_by_email(email)
            if existing is not None and existing.id != user.id:
                raise ForbiddenError("Korisnik sa ovom e-poštom već postoji")
            user.email = email
        for key, value in data.items():
            setattr(user, key, value)
        self.db.flush()
        return self._user_summary(user)

    def delete_user(self, user_id: UUID, *, actor_id: UUID) -> AdminUserDeleteResult:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Korisnik nije pronađen")
        if user.id == actor_id:
            raise ForbiddenError("Ne možete obrisati sopstveni nalog")
        if user.is_superuser:
            raise ForbiddenError("Platform admin nalog se ne može obrisati ovde")

        farm_count = int(
            self.db.scalar(select(func.count()).select_from(Farm).where(Farm.owner_id == user.id)) or 0
        )
        memberships = list(
            self.db.scalars(
                select(EnterpriseMembership).where(EnterpriseMembership.user_id == user.id)
            ).all()
        )

        # Farms reference users with RESTRICT — deactivate instead of hard-delete.
        if farm_count > 0:
            user.is_active = False
            for membership in memberships:
                membership.status = EnterpriseMembershipStatus.INACTIVE
            self.db.flush()
            return AdminUserDeleteResult(
                id=user.id,
                action="deactivated",
                message="Nalog ima zasade, pa je deaktiviran umesto trajnog brisanja.",
            )

        for membership in memberships:
            self.db.delete(membership)
        self.db.delete(user)
        self.db.flush()
        return AdminUserDeleteResult(
            id=user_id,
            action="deleted",
            message="Nalog je obrisan.",
        )

    def create_enterprise_org(self, payload: AdminEnterpriseOrgCreate) -> AdminEnterpriseOrgSummary:
        slug = payload.slug or "".join(ch.lower() if ch.isalnum() else "-" for ch in payload.name).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        if self.enterprise.get_org_by_slug(slug):
            slug = f"{slug}-{uuid4().hex[:6]}"
        org = ensure_organization(self.db, name=payload.name, slug=slug)
        if payload.country is not None:
            org.country = payload.country
        if payload.default_crop is not None:
            org.default_crop = payload.default_crop
        self.db.flush()
        return self._org_summary(org)

    def list_enterprise_orgs(self) -> list[AdminEnterpriseOrgSummary]:
        orgs = list(
            self.db.scalars(select(EnterpriseOrganization).order_by(EnterpriseOrganization.name)).all()
        )
        return [self._org_summary(org) for org in orgs]

    def get_enterprise_org(self, organization_id: UUID) -> AdminEnterpriseOrgSummary:
        org = self.enterprise.get_org(organization_id)
        if org is None:
            raise NotFoundError("Enterprise organizacija nije pronađena")
        return self._org_summary(org)

    def create_enterprise_user(self, payload: AdminEnterpriseUserCreate) -> AdminUserSummary:
        org = self.enterprise.get_org(payload.organization_id)
        if org is None or org.status != EnterpriseOrgStatus.ACTIVE:
            raise NotFoundError("Enterprise organizacija nije pronađena")
        user = self.users.get_by_email(payload.email.lower())
        if user is None:
            user = User(
                email=payload.email.lower(),
                full_name=payload.full_name,
                hashed_password=hash_password(payload.temporary_password),
                is_active=True,
                is_superuser=False,
                must_change_password=False,
            )
            self.users.add(user)
            self.db.flush()
        membership = self.enterprise.get_membership(org.id, user.id)
        if membership is None:
            membership = EnterpriseMembership(
                organization_id=org.id,
                user_id=user.id,
                role=payload.role,
                status=EnterpriseMembershipStatus.ACTIVE,
            )
            self.enterprise.add(membership)
        else:
            membership.role = payload.role
            membership.status = EnterpriseMembershipStatus.ACTIVE
        self.db.flush()
        return self._user_summary(user)

    def list_client_farms(self, organization_id: UUID | None = None) -> list[AdminClientFarmDetail]:
        farms = list(
            self.db.scalars(select(Farm).options(selectinload(Farm.parcels)).order_by(Farm.name)).all()
        )
        assigned_parcel_ids: set[UUID] = set()
        linked_farm_ids: set[UUID] = set()
        if organization_id is not None:
            assigned_parcel_ids = {
                a.parcel_id for a in self.enterprise.list_parcel_assignments(organization_id)
            }
            linked_farm_ids = {
                link.farm_id for link in self.enterprise.list_supplier_links(organization_id)
            }
        results: list[AdminClientFarmDetail] = []
        for farm in farms:
            owner = self.users.get_by_id(farm.owner_id)
            results.append(
                AdminClientFarmDetail(
                    farm_id=farm.id,
                    name=farm.name,
                    location_name=farm.location_name,
                    owner_id=farm.owner_id,
                    owner_email=owner.email if owner else None,
                    owner_name=owner.full_name if owner else None,
                    linked_as_supplier=farm.id in linked_farm_ids if organization_id else False,
                    parcels=[
                        AdminClientParcel(
                            parcel_id=parcel.id,
                            name=parcel.name,
                            area_hectares=parcel.area_hectares,
                            assigned_to_org=parcel.id in assigned_parcel_ids if organization_id else False,
                        )
                        for parcel in (farm.parcels or [])
                    ],
                )
            )
        return results

    def link_farm(
        self, organization_id: UUID, payload: AdminLinkFarmRequest, actor_id: UUID
    ) -> AdminSupplierLinkDetail:
        org = self.enterprise.get_org(organization_id)
        if org is None:
            raise NotFoundError("Enterprise organizacija nije pronađena")
        farm = self.db.get(Farm, payload.farm_id)
        if farm is None:
            raise NotFoundError("Gazdinstvo nije pronađeno")
        link = self.enterprise.get_supplier_by_farm(organization_id, farm.id)
        if link is None:
            link = EnterpriseSupplierLink(
                organization_id=organization_id,
                farm_id=farm.id,
                status=payload.status,
                internal_code=payload.internal_code,
                internal_group=payload.internal_group,
                assigned_by_id=actor_id,
            )
            self.enterprise.add(link)
        else:
            link.status = payload.status
            if payload.internal_code is not None:
                link.internal_code = payload.internal_code
            if payload.internal_group is not None:
                link.internal_group = payload.internal_group
        self.db.flush()

        parcel_ids: list[UUID] = []
        if payload.assign_all_parcels:
            parcel_ids = [
                p.id
                for p in self.db.scalars(select(Parcel).where(Parcel.farm_id == farm.id)).all()
            ]
        elif payload.parcel_ids:
            parcel_ids = list(payload.parcel_ids)

        if parcel_ids:
            self.assign_parcels(
                organization_id,
                AdminAssignParcelsRequest(parcel_ids=parcel_ids),
                actor_id,
            )

        self.enterprise.record_audit(
            organization_id=organization_id,
            actor_user_id=actor_id,
            action="admin_supplier_linked",
            entity_type="supplier_link",
            entity_id=link.id,
            details={"farm_id": str(farm.id), "parcel_count": len(parcel_ids)},
        )
        self.db.flush()
        return self._supplier_detail(organization_id, link)

    def assign_parcels(
        self, organization_id: UUID, payload: AdminAssignParcelsRequest, actor_id: UUID
    ) -> list[AdminParcelAssignmentDetail]:
        org = self.enterprise.get_org(organization_id)
        if org is None:
            raise NotFoundError("Enterprise organizacija nije pronađena")
        results: list[AdminParcelAssignmentDetail] = []
        for parcel_id in payload.parcel_ids:
            parcel = self.db.scalars(
                select(Parcel).options(selectinload(Parcel.farm)).where(Parcel.id == parcel_id)
            ).first()
            if parcel is None:
                raise NotFoundError(f"Parcela {parcel_id} nije pronađena")
            # Ensure supplier link exists before parcel assignment.
            link = self.enterprise.get_supplier_by_farm(organization_id, parcel.farm_id)
            if link is None:
                link = EnterpriseSupplierLink(
                    organization_id=organization_id,
                    farm_id=parcel.farm_id,
                    status=EnterpriseRelationshipStatus.ACTIVE,
                    assigned_by_id=actor_id,
                )
                self.enterprise.add(link)
                self.db.flush()
            existing = self.enterprise.get_assignment_by_parcel(organization_id, parcel.id)
            if existing is None:
                existing = EnterpriseParcelAssignment(
                    organization_id=organization_id,
                    farm_id=parcel.farm_id,
                    parcel_id=parcel.id,
                    status=payload.status,
                    assigned_by_id=actor_id,
                )
                self.enterprise.add(existing)
            else:
                existing.status = payload.status
            self.db.flush()
            results.append(self._assignment_detail(existing))
        self.enterprise.record_audit(
            organization_id=organization_id,
            actor_user_id=actor_id,
            action="admin_parcels_assigned",
            entity_type="parcel_assignment",
            details={"parcel_ids": [str(pid) for pid in payload.parcel_ids]},
        )
        self.db.flush()
        return results

    def list_org_suppliers(self, organization_id: UUID) -> list[AdminSupplierLinkDetail]:
        return [
            self._supplier_detail(organization_id, link)
            for link in self.enterprise.list_supplier_links(organization_id)
        ]

    def list_org_assignments(self, organization_id: UUID) -> list[AdminParcelAssignmentDetail]:
        return [
            self._assignment_detail(item)
            for item in self.enterprise.list_parcel_assignments(organization_id)
        ]

    def unlink_parcel(
        self, organization_id: UUID, assignment_id: UUID, actor_id: UUID
    ) -> AdminParcelAssignmentDetail:
        assignment = self.enterprise.get_parcel_assignment(organization_id, assignment_id)
        if assignment is None:
            raise NotFoundError("Dodela nije pronađena")
        assignment.status = EnterpriseAssignmentStatus.INACTIVE
        self.enterprise.record_audit(
            organization_id=organization_id,
            actor_user_id=actor_id,
            action="admin_parcel_unassigned",
            entity_type="parcel_assignment",
            entity_id=assignment.id,
            details={"parcel_id": str(assignment.parcel_id)},
        )
        self.db.flush()
        return self._assignment_detail(assignment)

    def _account_kinds(self, user: User) -> list[str]:
        kinds: list[str] = []
        if user.is_superuser:
            kinds.append("platform_admin")
        farm_count = int(
            self.db.scalar(select(func.count()).select_from(Farm).where(Farm.owner_id == user.id)) or 0
        )
        memberships = self.enterprise.list_memberships_for_user(user.id)
        if farm_count > 0 or (not memberships and not user.is_superuser):
            kinds.append("client")
        if memberships:
            kinds.append("enterprise")
        if not kinds:
            kinds.append("client")
        return kinds

    def _user_summary(self, user: User) -> AdminUserSummary:
        farms = list(
            self.db.scalars(
                select(Farm).options(selectinload(Farm.parcels)).where(Farm.owner_id == user.id)
            ).all()
        )
        memberships = self.enterprise.list_memberships_for_user(user.id)
        return AdminUserSummary(
            id=user.id,
            created_at=user.created_at,
            updated_at=user.updated_at,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            must_change_password=bool(user.must_change_password),
            account_kinds=self._account_kinds(user),
            farm_count=len(farms),
            farms=[
                AdminUserFarmSummary(
                    farm_id=farm.id,
                    name=farm.name,
                    parcel_count=len(farm.parcels or []),
                    location_name=farm.location_name,
                )
                for farm in farms
            ],
            enterprise_memberships=[
                AdminUserEnterpriseMembership(
                    organization_id=m.organization_id,
                    organization_name=m.organization.name if m.organization else "—",
                    role=m.role,
                    status=m.status,
                )
                for m in memberships
            ],
        )

    def _org_summary(self, org: EnterpriseOrganization) -> AdminEnterpriseOrgSummary:
        members = int(
            self.db.scalar(
                select(func.count())
                .select_from(EnterpriseMembership)
                .where(EnterpriseMembership.organization_id == org.id)
            )
            or 0
        )
        suppliers = int(
            self.db.scalar(
                select(func.count())
                .select_from(EnterpriseSupplierLink)
                .where(
                    EnterpriseSupplierLink.organization_id == org.id,
                    EnterpriseSupplierLink.status == EnterpriseRelationshipStatus.ACTIVE,
                )
            )
            or 0
        )
        parcels = int(
            self.db.scalar(
                select(func.count())
                .select_from(EnterpriseParcelAssignment)
                .where(
                    EnterpriseParcelAssignment.organization_id == org.id,
                    EnterpriseParcelAssignment.status == EnterpriseAssignmentStatus.ACTIVE,
                )
            )
            or 0
        )
        return AdminEnterpriseOrgSummary(
            id=org.id,
            created_at=org.created_at,
            updated_at=org.updated_at,
            name=org.name,
            slug=org.slug,
            status=org.status.value,
            member_count=members,
            supplier_count=suppliers,
            assigned_parcel_count=parcels,
            country=org.country,
        )

    def _supplier_detail(
        self, organization_id: UUID, link: EnterpriseSupplierLink
    ) -> AdminSupplierLinkDetail:
        farm = link.farm or self.db.get(Farm, link.farm_id)
        owner = self.users.get_by_id(farm.owner_id) if farm else None
        return AdminSupplierLinkDetail(
            id=link.id,
            created_at=link.created_at,
            updated_at=link.updated_at,
            farm_id=link.farm_id,
            farm_name=farm.name if farm else None,
            owner_name=owner.full_name if owner else None,
            owner_email=owner.email if owner else None,
            status=link.status,
            internal_code=link.internal_code,
            internal_group=link.internal_group,
            assigned_parcel_count=self.enterprise.count_active_assignments_for_farm(
                organization_id, link.farm_id
            ),
            assigned_at=link.assigned_at,
        )

    def _assignment_detail(
        self, item: EnterpriseParcelAssignment
    ) -> AdminParcelAssignmentDetail:
        parcel = item.parcel or self.db.get(Parcel, item.parcel_id)
        farm = item.farm or self.db.get(Farm, item.farm_id)
        owner = self.users.get_by_id(farm.owner_id) if farm else None
        return AdminParcelAssignmentDetail(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            farm_id=item.farm_id,
            parcel_id=item.parcel_id,
            farm_name=farm.name if farm else None,
            owner_name=owner.full_name if owner else None,
            parcel_name=parcel.name if parcel else None,
            status=item.status,
            assigned_at=item.assigned_at,
        )
