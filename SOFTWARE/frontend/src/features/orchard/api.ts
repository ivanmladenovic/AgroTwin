import { apiRequest } from '@/shared/lib/api'
import type {
  OrchardRow,
  OrchardTwin,
  Parcel,
  ParcelCreatePayload,
  ParcelUpdatePayload,
  ParcelWeather,
  ParcelSoilProfile,
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
