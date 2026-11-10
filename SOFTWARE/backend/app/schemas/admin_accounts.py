from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    EnterpriseAssignmentStatus,
    EnterpriseMembershipRole,
    EnterpriseMembershipStatus,
    EnterpriseRelationshipStatus,
)
from app.schemas.common import IDSchema


class AdminAccountsOverview(BaseModel):
    total_users: int
    client_users: int
    enterprise_users: int
    platform_admins: int
    enterprise_organizations: int
    active_supplier_links: int
    active_parcel_assignments: int


class AdminUserFarmSummary(BaseModel):
    farm_id: UUID
    name: str
    parcel_count: int
    location_name: str | None = None


class AdminUserEnterpriseMembership(BaseModel):
    organization_id: UUID
    organization_name: str
    role: EnterpriseMembershipRole
    status: EnterpriseMembershipStatus


class AdminUserSummary(IDSchema):
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    must_change_password: bool
    account_kinds: list[str]  # platform_admin | client | enterprise
    farm_count: int = 0
    farms: list[AdminUserFarmSummary] = Field(default_factory=list)
    enterprise_memberships: list[AdminUserEnterpriseMembership] = Field(default_factory=list)


class AdminClientCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    temporary_password: str = Field(min_length=8, max_length=128)
    farm_name: str | None = Field(default=None, max_length=255)
    location_name: str | None = Field(default=None, max_length=255)


class AdminEnterpriseOrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=128)
    country: str | None = None
    default_crop: str | None = None


class AdminEnterpriseUserCreate(BaseModel):
    organization_id: UUID
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    temporary_password: str = Field(min_length=8, max_length=128)
    role: EnterpriseMembershipRole = EnterpriseMembershipRole.ENTERPRISE_ADMIN


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
    must_change_password: bool | None = None
    temporary_password: str | None = Field(default=None, min_length=8, max_length=128)


class AdminUserDeleteResult(BaseModel):
    id: UUID
    action: str  # deleted | deactivated
    message: str


class AdminEnterpriseOrgSummary(IDSchema):
    name: str
    slug: str
    status: str
    member_count: int
    supplier_count: int
    assigned_parcel_count: int
    country: str | None = None


class AdminClientParcel(BaseModel):
    parcel_id: UUID
    name: str
    area_hectares: Decimal | None = None
    assigned_to_org: bool = False


class AdminClientFarmDetail(BaseModel):
    farm_id: UUID
    name: str
    location_name: str | None = None
    owner_id: UUID
    owner_email: EmailStr | None = None
    owner_name: str | None = None
    linked_as_supplier: bool = False
    parcels: list[AdminClientParcel] = Field(default_factory=list)


class AdminLinkFarmRequest(BaseModel):
    farm_id: UUID
    internal_code: str | None = Field(default=None, max_length=64)
    internal_group: str | None = Field(default=None, max_length=128)
    assign_all_parcels: bool = False
    parcel_ids: list[UUID] | None = None
    status: EnterpriseRelationshipStatus = EnterpriseRelationshipStatus.ACTIVE


class AdminAssignParcelsRequest(BaseModel):
    parcel_ids: list[UUID] = Field(min_length=1)
    status: EnterpriseAssignmentStatus = EnterpriseAssignmentStatus.ACTIVE


class AdminSupplierLinkDetail(IDSchema):
    farm_id: UUID
    farm_name: str | None = None
    owner_name: str | None = None
    owner_email: EmailStr | None = None
    status: EnterpriseRelationshipStatus
    internal_code: str | None = None
    internal_group: str | None = None
    assigned_parcel_count: int = 0
    assigned_at: datetime


class AdminParcelAssignmentDetail(IDSchema):
    farm_id: UUID
    parcel_id: UUID
    farm_name: str | None = None
    owner_name: str | None = None
    parcel_name: str | None = None
    status: EnterpriseAssignmentStatus
    assigned_at: datetime
