import { apiDownload, apiRequest } from '@/shared/lib/api'
import type {
  Activity,
  ActivityCreatePayload,
  ActivityFilters,
  ActivityUpdatePayload,
  CatalogItem,
  CostCreatePayload,
  CostItem,
  CostSummary,
} from '@/shared/api/types'

function queryString(filters: ActivityFilters = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value)
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export function listActivityTypes() {
  return apiRequest<CatalogItem[]>('/activity-types')
}

export function listCostCategories() {
  return apiRequest<CatalogItem[]>('/cost-categories')
}

export function listActivities(filters: ActivityFilters = {}) {
  return apiRequest<Activity[]>(`/activities${queryString(filters)}`)
}

export function getActivity(activityId: string) {
  return apiRequest<Activity>(`/activities/${activityId}`)
}

export function createActivity(payload: ActivityCreatePayload) {
  return apiRequest<Activity>('/activities', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateActivity(activityId: string, payload: ActivityUpdatePayload) {
  return apiRequest<Activity>(`/activities/${activityId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function addActivityCost(activityId: string, payload: CostCreatePayload) {
  return apiRequest<CostItem>(`/activities/${activityId}/costs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getCostSummary(parcelId?: string) {
  const query = parcelId ? `?parcel_id=${parcelId}` : ''
  return apiRequest<CostSummary>(`/costs/summary${query}`)
}

export function listCosts(parcelId?: string) {
  const query = parcelId ? `?parcel_id=${parcelId}` : ''
  return apiRequest<CostItem[]>(`/costs${query}`)
}

export function downloadCostsCsv(filters: ActivityFilters = {}) {
  return apiDownload(`/costs/export.csv${queryString(filters)}`, 'costs.csv')
}
