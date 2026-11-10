import { apiRequest } from '@/shared/lib/api'
import type {
  AdminAccountsOverview,
  AdminClientFarmDetail,
  AdminEnterpriseOrgSummary,
  AdminParcelAssignmentDetail,
  AdminSupplierLinkDetail,
  AdminUserSummary,
} from '@/shared/api/types'

export function getAdminOverview() {
  return apiRequest<AdminAccountsOverview>('/admin/accounts/overview')
}

export function listAdminUsers(q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  return apiRequest<AdminUserSummary[]>(`/admin/accounts/users${qs}`)
}

export function createAdminClient(payload: {
  email: string
  full_name: string
  temporary_password: string
  farm_name?: string
  location_name?: string
}) {
  return apiRequest<AdminUserSummary>('/admin/accounts/clients', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdminUser(
  userId: string,
  payload: {
    email?: string
    full_name?: string
    is_active?: boolean
    must_change_password?: boolean
    temporary_password?: string
  },
) {
  return apiRequest<AdminUserSummary>(`/admin/accounts/users/${userId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteAdminUser(userId: string) {
  return apiRequest<{ id: string; action: 'deleted' | 'deactivated'; message: string }>(
    `/admin/accounts/users/${userId}`,
    { method: 'DELETE' },
  )
}

export function listAdminEnterpriseOrgs() {
  return apiRequest<AdminEnterpriseOrgSummary[]>('/admin/accounts/enterprise-orgs')
}

export function createAdminEnterpriseOrg(payload: {
  name: string
  slug?: string
  country?: string
  default_crop?: string
}) {
  return apiRequest<AdminEnterpriseOrgSummary>('/admin/accounts/enterprise-orgs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function createAdminEnterpriseUser(payload: {
  organization_id: string
  email: string
  full_name: string
  temporary_password: string
  role?: string
}) {
  return apiRequest<AdminUserSummary>('/admin/accounts/enterprise-users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listAdminFarms(organizationId?: string) {
  const qs = organizationId ? `?organization_id=${organizationId}` : ''
  return apiRequest<AdminClientFarmDetail[]>(`/admin/accounts/farms${qs}`)
}

export function listAdminOrgSuppliers(organizationId: string) {
  return apiRequest<AdminSupplierLinkDetail[]>(
    `/admin/accounts/enterprise-orgs/${organizationId}/suppliers`,
  )
}

export function listAdminOrgAssignments(organizationId: string) {
  return apiRequest<AdminParcelAssignmentDetail[]>(
    `/admin/accounts/enterprise-orgs/${organizationId}/assignments`,
  )
}

export function linkAdminFarm(
  organizationId: string,
  payload: {
    farm_id: string
    internal_code?: string
    internal_group?: string
    assign_all_parcels?: boolean
    parcel_ids?: string[]
  },
) {
  return apiRequest<AdminSupplierLinkDetail>(
    `/admin/accounts/enterprise-orgs/${organizationId}/link-farm`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function assignAdminParcels(
  organizationId: string,
  payload: { parcel_ids: string[] },
) {
  return apiRequest<AdminParcelAssignmentDetail[]>(
    `/admin/accounts/enterprise-orgs/${organizationId}/assign-parcels`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function deactivateAdminAssignment(organizationId: string, assignmentId: string) {
  return apiRequest<AdminParcelAssignmentDetail>(
    `/admin/accounts/enterprise-orgs/${organizationId}/assignments/${assignmentId}/deactivate`,
    { method: 'POST' },
  )
}
