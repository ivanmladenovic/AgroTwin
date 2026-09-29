import { apiDownload, apiRequest, apiUpload, fetchObjectUrl } from '@/shared/lib/api'
import type {
  Activity,
  ActivityCreatePayload,
  ActivityFilters,
  ActivityUpdatePayload,
  CatalogItem,
  CostCreatePayload,
  CostItem,
  CostSummary,
  SoilLabAnalysis,
  Subsidy,
  SubsidyCreatePayload,
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

export function uploadSoilAnalysis(
  activityId: string,
  payload: { file: File; tree_id: string; sampled_on: string },
) {
  const form = new FormData()
  form.append('file', payload.file)
  form.append('tree_id', payload.tree_id)
  form.append('sampled_on', payload.sampled_on)
  return apiUpload<SoilLabAnalysis>(`/activities/${activityId}/soil-analyses`, form)
}

export function listParcelSoilAnalyses(parcelId: string) {
  return apiRequest<SoilLabAnalysis[]>(`/parcels/${parcelId}/soil-analyses`)
}

export function uploadParcelSoilAnalysis(
  parcelId: string,
  payload: { file: File; tree_id: string; sampled_on: string },
) {
  const form = new FormData()
  form.append('file', payload.file)
  form.append('tree_id', payload.tree_id)
  form.append('sampled_on', payload.sampled_on)
  return apiUpload<SoilLabAnalysis>(`/parcels/${parcelId}/soil-analyses`, form)
}

export function downloadSoilAnalysis(analysis: SoilLabAnalysis) {
  return apiDownload(`/soil-analyses/${analysis.id}/file`, analysis.original_filename)
}

export async function openSoilAnalysis(analysis: SoilLabAnalysis) {
  const popup = window.open('about:blank', '_blank')
  try {
    const url = await fetchObjectUrl(`/soil-analyses/${analysis.id}/file`)
    if (popup && !popup.closed) {
      popup.location.replace(url)
      return true
    }
    // Popup blocked — fall back to download without leaving a dangling blank tab.
    popup?.close()
    return false
  } catch (error) {
    popup?.close()
    throw error
  }
}

export function deleteSoilAnalysis(analysisId: string) {
  return apiRequest<void>(`/soil-analyses/${analysisId}`, { method: 'DELETE' })
}

export function listSubsidies(parcelId?: string) {
  const query = parcelId ? `?parcel_id=${parcelId}` : ''
  return apiRequest<Subsidy[]>(`/subsidies${query}`)
}

export function createSubsidy(payload: SubsidyCreatePayload) {
  return apiRequest<Subsidy>('/subsidies', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteSubsidy(subsidyId: string) {
  return apiRequest<void>(`/subsidies/${subsidyId}`, { method: 'DELETE' })
}
