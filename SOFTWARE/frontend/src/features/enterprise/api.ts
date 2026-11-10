import { apiDownload, apiRequest } from '@/shared/lib/api'
import type {
  EnterpriseAggregateReport,
  EnterpriseAssignableParcel,
  EnterpriseDashboardKPIs,
  EnterpriseDataQuality,
  EnterpriseFollowUp,
  EnterpriseFarmCandidate,
  EnterpriseMapParcel,
  EnterpriseMembership,
  EnterpriseMeResponse,
  EnterpriseAlertReviewResult,
  EnterpriseAlertWatchPage,
  EnterpriseMonitoringCenter,
  EnterpriseOrganization,
  EnterpriseOtkupOverview,
  EnterpriseParcelDetail,
  EnterpriseParcelSummary,
  EnterprisePlanningSeason,
  EnterpriseProductionAnalytics,
  EnterprisePurchase,
  EnterprisePurchaseCurrency,
  EnterpriseQuantityBasis,
  EnterpriseSupplierLink,
  EnterpriseSupplierPrice,
  EnterpriseYieldComparison,
  EnterpriseYieldPlan,
  OrchardTwin,
  User,
} from '@/shared/api/types'

export function getEnterpriseMe() {
  return apiRequest<EnterpriseMeResponse>('/enterprise/me')
}

export function changeEnterprisePassword(payload: {
  current_password: string
  new_password: string
}) {
  return apiRequest<User>('/enterprise/change-password', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getEnterpriseOrganization(organizationId: string) {
  return apiRequest<EnterpriseOrganization>(`/enterprise/organizations/${organizationId}`)
}

export function updateEnterpriseOrganization(
  organizationId: string,
  payload: Partial<EnterpriseOrganization>,
) {
  return apiRequest<EnterpriseOrganization>(`/enterprise/organizations/${organizationId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function getEnterpriseDashboard(organizationId: string, year?: number) {
  const qs = year ? `?year=${year}` : ''
  return apiRequest<EnterpriseDashboardKPIs>(
    `/enterprise/organizations/${organizationId}/dashboard${qs}`,
  )
}

export function getEnterpriseMapParcels(organizationId: string) {
  return apiRequest<EnterpriseMapParcel[]>(
    `/enterprise/organizations/${organizationId}/map-parcels`,
  )
}

export type EnterpriseMonitoringParams = {
  year?: number
  farm_id?: string
  parcel_id?: string
  category?: string
  review_status?: string
  severity?: string
  date_from?: string
  date_to?: string
}

export function getEnterpriseMonitoring(
  organizationId: string,
  params?: EnterpriseMonitoringParams,
) {
  const search = new URLSearchParams()
  if (params?.year) search.set('year', String(params.year))
  if (params?.farm_id) search.set('farm_id', params.farm_id)
  if (params?.parcel_id) search.set('parcel_id', params.parcel_id)
  if (params?.category) search.set('category', params.category)
  if (params?.review_status) search.set('review_status', params.review_status)
  if (params?.severity) search.set('severity', params.severity)
  if (params?.date_from) search.set('date_from', params.date_from)
  if (params?.date_to) search.set('date_to', params.date_to)
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterpriseMonitoringCenter>(
    `/enterprise/organizations/${organizationId}/monitoring${qs}`,
  )
}

export function getEnterpriseProductionAnalytics(
  organizationId: string,
  params?: { years_back?: number; year?: number; parcel_ids?: string[] },
) {
  const search = new URLSearchParams()
  if (params?.years_back) search.set('years_back', String(params.years_back))
  if (params?.year) search.set('year', String(params.year))
  for (const id of params?.parcel_ids ?? []) {
    search.append('parcel_ids', id)
  }
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterpriseProductionAnalytics>(
    `/enterprise/organizations/${organizationId}/production-analytics${qs}`,
  )
}

export function createEnterpriseAggregateReport(
  organizationId: string,
  payload: { parcel_ids: string[]; year?: number },
) {
  return apiRequest<EnterpriseAggregateReport>(
    `/enterprise/organizations/${organizationId}/reports/aggregate`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function listEnterpriseMemberships(organizationId: string) {
  return apiRequest<EnterpriseMembership[]>(
    `/enterprise/organizations/${organizationId}/memberships`,
  )
}

export function addEnterpriseMembership(
  organizationId: string,
  payload: {
    email: string
    full_name: string
    role: string
    temporary_password?: string
  },
) {
  return apiRequest<EnterpriseMembership>(
    `/enterprise/organizations/${organizationId}/memberships`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function getEnterpriseDataQuality(organizationId: string, year?: number, bucket?: string) {
  const params = new URLSearchParams()
  if (year) params.set('year', String(year))
  if (bucket) params.set('bucket', bucket)
  const qs = params.toString()
  return apiRequest<EnterpriseDataQuality>(
    `/enterprise/organizations/${organizationId}/data-quality${qs ? `?${qs}` : ''}`,
  )
}

export function listEnterpriseFollowUps(
  organizationId: string,
  params?: {
    status?: string
    farm_id?: string
    parcel_id?: string
    assignee_user_id?: string
    due?: string
  },
) {
  const search = new URLSearchParams()
  if (params?.status) search.set('status', params.status)
  if (params?.farm_id) search.set('farm_id', params.farm_id)
  if (params?.parcel_id) search.set('parcel_id', params.parcel_id)
  if (params?.assignee_user_id) search.set('assignee_user_id', params.assignee_user_id)
  if (params?.due) search.set('due', params.due)
  const qs = search.toString()
  return apiRequest<EnterpriseFollowUp[]>(
    `/enterprise/organizations/${organizationId}/follow-ups${qs ? `?${qs}` : ''}`,
  )
}

export function createEnterpriseFollowUp(
  organizationId: string,
  payload: {
    title: string
    body?: string | null
    status?: string
    farm_id?: string | null
    parcel_id?: string | null
    alert_id?: string | null
    assignee_user_id?: string | null
    due_on?: string | null
  },
) {
  return apiRequest<EnterpriseFollowUp>(`/enterprise/organizations/${organizationId}/follow-ups`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateEnterpriseFollowUp(
  organizationId: string,
  taskId: string,
  payload: {
    title?: string
    body?: string | null
    status?: string
    farm_id?: string | null
    parcel_id?: string | null
    assignee_user_id?: string | null
    due_on?: string | null
  },
) {
  return apiRequest<EnterpriseFollowUp>(
    `/enterprise/organizations/${organizationId}/follow-ups/${taskId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function downloadEnterpriseAlertCsv(organizationId: string, params: URLSearchParams) {
  const qs = params.toString()
  return apiDownload(
    `/enterprise/organizations/${organizationId}/exports/intelligence-alerts.csv${qs ? `?${qs}` : ''}`,
    'enterprise-alerts.csv',
  )
}

export function updateEnterpriseMembership(
  organizationId: string,
  membershipId: string,
  payload: { role?: string; status?: string },
) {
  return apiRequest<EnterpriseMembership>(
    `/enterprise/organizations/${organizationId}/memberships/${membershipId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function listEnterpriseSuppliers(organizationId: string, params?: { q?: string; status?: string }) {
  const search = new URLSearchParams()
  if (params?.q) search.set('q', params.q)
  if (params?.status) search.set('status', params.status)
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterpriseSupplierLink[]>(
    `/enterprise/organizations/${organizationId}/suppliers${qs}`,
  )
}

export function getEnterpriseSupplier(organizationId: string, linkId: string) {
  return apiRequest<EnterpriseSupplierLink>(
    `/enterprise/organizations/${organizationId}/suppliers/${linkId}`,
  )
}

export function createEnterpriseSupplier(
  organizationId: string,
  payload: {
    farm_id: string
    internal_code?: string
    internal_group?: string
    internal_notes?: string
    status?: string
  },
) {
  return apiRequest<EnterpriseSupplierLink>(
    `/enterprise/organizations/${organizationId}/suppliers`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function updateEnterpriseSupplier(
  organizationId: string,
  linkId: string,
  payload: {
    status?: string
    internal_code?: string | null
    internal_group?: string | null
    internal_notes?: string | null
  },
) {
  return apiRequest<EnterpriseSupplierLink>(
    `/enterprise/organizations/${organizationId}/suppliers/${linkId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export function listLinkableFarms(organizationId: string, q?: string) {
  const qs = q ? `?q=${encodeURIComponent(q)}` : ''
  return apiRequest<EnterpriseFarmCandidate[]>(
    `/enterprise/organizations/${organizationId}/farms/linkable${qs}`,
  )
}

export function listAssignableParcels(organizationId: string, farmId: string) {
  return apiRequest<EnterpriseAssignableParcel[]>(
    `/enterprise/organizations/${organizationId}/farms/${farmId}/assignable-parcels`,
  )
}

export function assignEnterpriseParcel(
  organizationId: string,
  payload: { parcel_id: string; status?: string },
) {
  return apiRequest(`/enterprise/organizations/${organizationId}/assignments`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listEnterpriseParcels(
  organizationId: string,
  params?: { q?: string; farm_id?: string },
) {
  const search = new URLSearchParams()
  if (params?.q) search.set('q', params.q)
  if (params?.farm_id) search.set('farm_id', params.farm_id)
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterpriseParcelSummary[]>(
    `/enterprise/organizations/${organizationId}/parcels${qs}`,
  )
}

export function getEnterpriseParcel(organizationId: string, parcelId: string) {
  return apiRequest<EnterpriseParcelDetail>(
    `/enterprise/organizations/${organizationId}/parcels/${parcelId}`,
  )
}

export function getEnterpriseParcelTwin(organizationId: string, parcelId: string) {
  return apiRequest<OrchardTwin>(
    `/enterprise/organizations/${organizationId}/parcels/${parcelId}/twin`,
  )
}

export function listEnterpriseSeasons(organizationId: string) {
  return apiRequest<EnterprisePlanningSeason[]>(
    `/enterprise/organizations/${organizationId}/seasons`,
  )
}

export function createEnterpriseSeason(
  organizationId: string,
  payload: { year: number; name: string; supply_target_kg?: number | null },
) {
  return apiRequest<EnterprisePlanningSeason>(
    `/enterprise/organizations/${organizationId}/seasons`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function listEnterpriseYieldPlans(organizationId: string, seasonId?: string) {
  const qs = seasonId ? `?season_id=${seasonId}` : ''
  return apiRequest<EnterpriseYieldPlan[]>(
    `/enterprise/organizations/${organizationId}/yield-plans${qs}`,
  )
}

export function createEnterpriseYieldPlan(
  organizationId: string,
  payload: {
    planning_season_id: string
    name: string
    description?: string
    scenario_type: string
    parcel_ids?: string[]
    assumptions?: Record<string, unknown>
  },
) {
  return apiRequest<EnterpriseYieldPlan>(
    `/enterprise/organizations/${organizationId}/yield-plans`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function getEnterpriseYieldPlan(organizationId: string, planId: string) {
  return apiRequest<EnterpriseYieldPlan>(
    `/enterprise/organizations/${organizationId}/yield-plans/${planId}`,
  )
}

export function recalculateEnterpriseYieldPlan(organizationId: string, planId: string) {
  return apiRequest<EnterpriseYieldPlan>(
    `/enterprise/organizations/${organizationId}/yield-plans/${planId}/recalculate`,
    { method: 'POST' },
  )
}

export function compareEnterpriseYieldPlan(organizationId: string, planId: string) {
  return apiRequest<EnterpriseYieldComparison>(
    `/enterprise/organizations/${organizationId}/yield-plans/${planId}/compare`,
  )
}

export function downloadEnterpriseParcelsCsv(organizationId: string) {
  return apiDownload(
    `/enterprise/organizations/${organizationId}/exports/parcels.csv`,
    'enterprise-parcels.csv',
  )
}

export function downloadEnterpriseYieldPlanCsv(organizationId: string, planId: string) {
  return apiDownload(
    `/enterprise/organizations/${organizationId}/exports/yield-plans/${planId}.csv`,
    `enterprise-plan-${planId}.csv`,
  )
}

export function getEnterpriseOtkupOverview(organizationId: string, year?: number) {
  const qs = year ? `?year=${year}` : ''
  return apiRequest<EnterpriseOtkupOverview>(
    `/enterprise/organizations/${organizationId}/otkup${qs}`,
  )
}

export function upsertEnterpriseOtkupPrice(
  organizationId: string,
  payload: {
    farm_id: string
    season_year: number
    currency: EnterprisePurchaseCurrency
    price_bruto_per_kg?: string | null
    price_neto_per_kg?: string | null
    notes?: string | null
  },
) {
  return apiRequest<EnterpriseSupplierPrice>(
    `/enterprise/organizations/${organizationId}/otkup/prices`,
    { method: 'PUT', body: JSON.stringify(payload) },
  )
}

export function listEnterpriseOtkupPurchases(
  organizationId: string,
  params?: { year?: number; farm_id?: string },
) {
  const search = new URLSearchParams()
  if (params?.year) search.set('year', String(params.year))
  if (params?.farm_id) search.set('farm_id', params.farm_id)
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterprisePurchase[]>(
    `/enterprise/organizations/${organizationId}/otkup/purchases${qs}`,
  )
}

export function createEnterpriseOtkupPurchase(
  organizationId: string,
  payload: {
    farm_id: string
    purchased_on: string
    quantity_kg: string
    quantity_basis: EnterpriseQuantityBasis
    currency?: EnterprisePurchaseCurrency
    unit_price_per_kg?: string | null
    total_amount?: string | null
    notes?: string | null
  },
) {
  return apiRequest<EnterprisePurchase>(
    `/enterprise/organizations/${organizationId}/otkup/purchases`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export type EnterpriseAlertWatchParams = {
  date_from?: string
  date_to?: string
  farm_id?: string
  parcel_id?: string
  index?: string
  severity?: string
  alert_status?: string
  review_status?: string
  limit?: number
  offset?: number
}

export function getEnterpriseAlertWatch(
  organizationId: string,
  params?: EnterpriseAlertWatchParams,
) {
  const search = new URLSearchParams()
  if (params?.date_from) search.set('date_from', params.date_from)
  if (params?.date_to) search.set('date_to', params.date_to)
  if (params?.farm_id) search.set('farm_id', params.farm_id)
  if (params?.parcel_id) search.set('parcel_id', params.parcel_id)
  if (params?.index) search.set('index', params.index)
  if (params?.severity) search.set('severity', params.severity)
  if (params?.alert_status) search.set('alert_status', params.alert_status)
  if (params?.review_status) search.set('review_status', params.review_status)
  if (params?.limit) search.set('limit', String(params.limit))
  if (params?.offset) search.set('offset', String(params.offset))
  const qs = search.toString() ? `?${search}` : ''
  return apiRequest<EnterpriseAlertWatchPage>(
    `/enterprise/organizations/${organizationId}/intelligence-alerts${qs}`,
  )
}

export function reviewEnterpriseAlert(
  organizationId: string,
  alertId: string,
  note?: string,
) {
  return apiRequest<EnterpriseAlertReviewResult>(
    `/enterprise/organizations/${organizationId}/intelligence-alerts/${alertId}/review`,
    { method: 'POST', body: JSON.stringify({ note: note?.trim() ? note.trim() : null }) },
  )
}

export function deleteEnterpriseOtkupPurchase(organizationId: string, purchaseId: string) {
  return apiRequest<{ detail: string }>(
    `/enterprise/organizations/${organizationId}/otkup/purchases/${purchaseId}`,
    { method: 'DELETE' },
  )
}
