import { apiRequest } from '@/shared/lib/api'
import type {
  OrchardRow,
  OrchardTwin,
  Parcel,
  ParcelAlert,
  ParcelAnalysisRun,
  ParcelCreatePayload,
  ParcelIntelligence,
  ParcelSatelliteMonitoring,
  ParcelUpdatePayload,
  ParcelWeather,
  ParcelSoilProfile,
  SatelliteHistory,
  SatelliteObservation,
  SatelliteSample,
  SatelliteSyncResult,
  TreeDetail,
  TreeJournal,
  TreeOption,
} from '@/shared/api/types'

export function listParcels() {
  return apiRequest<Parcel[]>('/parcels')
}

export function createParcel(payload: ParcelCreatePayload) {
  return apiRequest<Parcel>('/parcels', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateParcel(parcelId: string, payload: ParcelUpdatePayload) {
  return apiRequest<Parcel>(`/parcels/${parcelId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteParcel(parcelId: string) {
  return apiRequest<void>(`/parcels/${parcelId}`, { method: 'DELETE' })
}

export function getParcel(parcelId: string) {
  return apiRequest<Parcel>(`/parcels/${parcelId}`)
}

export function getOrchardTwin(parcelId: string) {
  return apiRequest<OrchardTwin>(`/parcels/${parcelId}/twin`)
}

export function getTreeDetail(parcelId: string, treeId: string) {
  return apiRequest<TreeDetail>(`/parcels/${parcelId}/trees/${treeId}`)
}

export function getTreeJournal(parcelId: string, treeId: string) {
  return apiRequest<TreeJournal>(`/parcels/${parcelId}/trees/${treeId}/journal`)
}

export function listParcelRows(parcelId: string) {
  return apiRequest<OrchardRow[]>(`/parcels/${parcelId}/rows`)
}

export function listParcelTrees(parcelId: string, rowId?: string) {
  const query = rowId ? `?row_id=${rowId}` : ''
  return apiRequest<TreeOption[]>(`/parcels/${parcelId}/trees${query}`)
}

export function getParcelWeather(parcelId: string) {
  return apiRequest<ParcelWeather>(`/parcels/${parcelId}/weather`)
}

export function getParcelSoilProfile(parcelId: string) {
  return apiRequest<ParcelSoilProfile>(`/parcels/${parcelId}/soil/profile`)
}

export function refreshParcelSoilProfile(parcelId: string) {
  return apiRequest<ParcelSoilProfile>(`/parcels/${parcelId}/soil/refresh`, { method: 'POST' })
}

/** Warm Yr weather + SoilGrids caches after parcel location/boundary is known. */
export async function warmParcelEnvironment(parcelId: string) {
  await Promise.allSettled([getParcelWeather(parcelId), getParcelSoilProfile(parcelId)])
}

export function getParcelSatelliteMonitoring(parcelId: string) {
  return apiRequest<ParcelSatelliteMonitoring>(`/parcels/${parcelId}/satellite`)
}

export function getParcelSatelliteHistory(
  parcelId: string,
  params?: { dateFrom?: string; dateTo?: string; date_from?: string; date_to?: string },
) {
  const q = new URLSearchParams()
  const from = params?.dateFrom ?? params?.date_from
  const to = params?.dateTo ?? params?.date_to
  if (from) q.set('date_from', from)
  if (to) q.set('date_to', to)
  const query = q.toString()
  return apiRequest<SatelliteHistory>(`/parcels/${parcelId}/satellite/history${query ? `?${query}` : ''}`)
}

export function refreshParcelSatellite(parcelId: string) {
  return apiRequest<SatelliteSyncResult>(`/parcels/${parcelId}/satellite/refresh`, { method: 'POST' })
}

export function getSatelliteObservation(observationId: string) {
  return apiRequest<SatelliteObservation>(`/satellite/observations/${observationId}`)
}

export function sampleSatelliteObservation(
  observationId: string,
  params: { longitude: number; latitude: number; index?: string },
) {
  const q = new URLSearchParams({
    longitude: String(params.longitude),
    latitude: String(params.latitude),
    index: params.index ?? 'ndvi',
  })
  return apiRequest<SatelliteSample>(`/satellite/observations/${observationId}/sample?${q}`)
}

export function getParcelIntelligence(parcelId: string) {
  return apiRequest<ParcelIntelligence>(`/parcels/${parcelId}/intelligence`)
}

export function requestParcelIntelligence(parcelId: string) {
  return apiRequest<ParcelAnalysisRun>(`/parcels/${parcelId}/intelligence/analyze`, { method: 'POST' })
}

export function acknowledgeIntelligenceAlert(alertId: string) {
  return apiRequest<ParcelAlert>(`/intelligence/alerts/${alertId}/acknowledge`, { method: 'POST' })
}

export function resolveIntelligenceAlert(alertId: string) {
  return apiRequest<ParcelAlert>(`/intelligence/alerts/${alertId}/resolve`, { method: 'POST' })
}
