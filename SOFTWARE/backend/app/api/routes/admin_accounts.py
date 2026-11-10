from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentSuperuser, DBSession
from app.schemas.admin_accounts import (
    AdminAccountsOverview,
    AdminAssignParcelsRequest,
    AdminClientCreate,
    AdminClientFarmDetail,
    AdminEnterpriseOrgCreate,
    AdminEnterpriseOrgSummary,
    AdminEnterpriseUserCreate,
    AdminLinkFarmRequest,
    AdminParcelAssignmentDetail,
    AdminSupplierLinkDetail,
    AdminUserDeleteResult,
    AdminUserSummary,
    AdminUserUpdate,
)
from app.services.admin_accounts import AdminAccountsService

router = APIRouter(prefix="/admin/accounts", tags=["admin-accounts"])


@router.get("/overview", response_model=AdminAccountsOverview)
def overview(_admin: CurrentSuperuser, db: DBSession) -> AdminAccountsOverview:
    return AdminAccountsService(db).overview()


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(
    _admin: CurrentSuperuser, db: DBSession, q: str | None = None
) -> list[AdminUserSummary]:
    return AdminAccountsService(db).list_users(q=q)


@router.get("/users/{user_id}", response_model=AdminUserSummary)
def get_user(user_id: UUID, _admin: CurrentSuperuser, db: DBSession) -> AdminUserSummary:
    return AdminAccountsService(db).get_user(user_id)


@router.post("/clients", response_model=AdminUserSummary, status_code=201)
def create_client(
    payload: AdminClientCreate, _admin: CurrentSuperuser, db: DBSession
) -> AdminUserSummary:
    result = AdminAccountsService(db).create_client(payload)
    db.commit()
    return result


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
def update_user(
    user_id: UUID, payload: AdminUserUpdate, _admin: CurrentSuperuser, db: DBSession
) -> AdminUserSummary:
    result = AdminAccountsService(db).update_user(user_id, payload)
    db.commit()
    return result


@router.delete("/users/{user_id}", response_model=AdminUserDeleteResult)
def delete_user(
    user_id: UUID, admin: CurrentSuperuser, db: DBSession
) -> AdminUserDeleteResult:
    result = AdminAccountsService(db).delete_user(user_id, actor_id=admin.id)
    db.commit()
    return result


@router.get("/enterprise-orgs", response_model=list[AdminEnterpriseOrgSummary])
def list_enterprise_orgs(
    _admin: CurrentSuperuser, db: DBSession
) -> list[AdminEnterpriseOrgSummary]:
    return AdminAccountsService(db).list_enterprise_orgs()


@router.get("/enterprise-orgs/{organization_id}", response_model=AdminEnterpriseOrgSummary)
def get_enterprise_org(
    organization_id: UUID, _admin: CurrentSuperuser, db: DBSession
) -> AdminEnterpriseOrgSummary:
    return AdminAccountsService(db).get_enterprise_org(organization_id)


@router.post("/enterprise-orgs", response_model=AdminEnterpriseOrgSummary, status_code=201)
def create_enterprise_org(
    payload: AdminEnterpriseOrgCreate, _admin: CurrentSuperuser, db: DBSession
) -> AdminEnterpriseOrgSummary:
    result = AdminAccountsService(db).create_enterprise_org(payload)
    db.commit()
    return result


@router.post("/enterprise-users", response_model=AdminUserSummary, status_code=201)
def create_enterprise_user(
    payload: AdminEnterpriseUserCreate, _admin: CurrentSuperuser, db: DBSession
) -> AdminUserSummary:
    result = AdminAccountsService(db).create_enterprise_user(payload)
    db.commit()
    return result


@router.get("/farms", response_model=list[AdminClientFarmDetail])
def list_farms(
    _admin: CurrentSuperuser,
    db: DBSession,
    organization_id: UUID | None = Query(default=None),
) -> list[AdminClientFarmDetail]:
    return AdminAccountsService(db).list_client_farms(organization_id)


@router.get(
    "/enterprise-orgs/{organization_id}/suppliers",
    response_model=list[AdminSupplierLinkDetail],
)
def list_org_suppliers(
    organization_id: UUID, _admin: CurrentSuperuser, db: DBSession
) -> list[AdminSupplierLinkDetail]:
    return AdminAccountsService(db).list_org_suppliers(organization_id)


@router.get(
    "/enterprise-orgs/{organization_id}/assignments",
    response_model=list[AdminParcelAssignmentDetail],
)
def list_org_assignments(
    organization_id: UUID, _admin: CurrentSuperuser, db: DBSession
) -> list[AdminParcelAssignmentDetail]:
    return AdminAccountsService(db).list_org_assignments(organization_id)


@router.post(
    "/enterprise-orgs/{organization_id}/link-farm",
    response_model=AdminSupplierLinkDetail,
    status_code=201,
)
def link_farm(
    organization_id: UUID,
    payload: AdminLinkFarmRequest,
    admin: CurrentSuperuser,
    db: DBSession,
) -> AdminSupplierLinkDetail:
    result = AdminAccountsService(db).link_farm(organization_id, payload, admin.id)
    db.commit()
    return result


@router.post(
    "/enterprise-orgs/{organization_id}/assign-parcels",
    response_model=list[AdminParcelAssignmentDetail],
    status_code=201,
)
def assign_parcels(
    organization_id: UUID,
    payload: AdminAssignParcelsRequest,
    admin: CurrentSuperuser,
    db: DBSession,
) -> list[AdminParcelAssignmentDetail]:
    result = AdminAccountsService(db).assign_parcels(organization_id, payload, admin.id)
    db.commit()
    return result


@router.post(
    "/enterprise-orgs/{organization_id}/assignments/{assignment_id}/deactivate",
    response_model=AdminParcelAssignmentDetail,
)
def deactivate_assignment(
    organization_id: UUID,
    assignment_id: UUID,
    admin: CurrentSuperuser,
    db: DBSession,
) -> AdminParcelAssignmentDetail:
    result = AdminAccountsService(db).unlink_parcel(organization_id, assignment_id, admin.id)
    db.commit()
    return result
