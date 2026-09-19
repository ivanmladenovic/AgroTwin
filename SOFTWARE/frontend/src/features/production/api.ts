import { apiDownload, apiRequest } from '@/shared/lib/api'
import type { HarvestEvent, HarvestEventPayload, ParcelProduction } from '@/shared/api/types'

export function getParcelProduction(parcelId: string, year: number) {
  return apiRequest<ParcelProduction>(`/parcels/${parcelId}/production?year=${year}`)
}

export function listHarvests(parcelId: string, year: number) {
  return apiRequest<HarvestEvent[]>(`/parcels/${parcelId}/harvests?year=${year}`)
}

export function getHarvest(parcelId: string, harvestId: string) {
  return apiRequest<HarvestEvent>(`/parcels/${parcelId}/harvests/${harvestId}`)
}

export function createHarvest(parcelId: string, payload: HarvestEventPayload) {
  return apiRequest<HarvestEvent>(`/parcels/${parcelId}/harvests`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateHarvest(parcelId: string, harvestId: string, payload: HarvestEventPayload) {
  return apiRequest<HarvestEvent>(`/parcels/${parcelId}/harvests/${harvestId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteHarvest(parcelId: string, harvestId: string) {
  return apiRequest<void>(`/parcels/${parcelId}/harvests/${harvestId}`, { method: 'DELETE' })
}

export function downloadProductionCsv(parcelId: string, year: number) {
  return apiDownload(`/parcels/${parcelId}/harvests/export.csv?year=${year}`, `proizvodnja-${year}.csv`)
}
