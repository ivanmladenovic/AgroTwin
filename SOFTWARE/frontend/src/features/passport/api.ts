import { apiRequest } from '@/shared/lib/api'
import type {
  HarvestLot,
  HarvestLotCreatePayload,
  HarvestLotUpdatePayload,
  PublicPassport,
} from '@/shared/api/types'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1'

export function listHarvestLots(filters: { parcel_id?: string; harvest_id?: string } = {}) {
  const params = new URLSearchParams()
  if (filters.parcel_id) params.set('parcel_id', filters.parcel_id)
  if (filters.harvest_id) params.set('harvest_id', filters.harvest_id)
  const qs = params.toString()
  return apiRequest<HarvestLot[]>(`/harvest-lots${qs ? `?${qs}` : ''}`)
}

export function getHarvestLot(lotId: string) {
  return apiRequest<HarvestLot>(`/harvest-lots/${lotId}`)
}

export function getLotForHarvest(harvestId: string) {
  return apiRequest<HarvestLot | null>(`/harvests/${harvestId}/lot`)
}

export function createHarvestLot(payload: HarvestLotCreatePayload) {
  return apiRequest<HarvestLot>('/harvest-lots', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateHarvestLot(lotId: string, payload: HarvestLotUpdatePayload) {
  return apiRequest<HarvestLot>(`/harvest-lots/${lotId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function finalizeHarvestLot(lotId: string) {
  return apiRequest<HarvestLot>(`/harvest-lots/${lotId}/finalize`, { method: 'POST' })
}

export function revokeHarvestLot(lotId: string) {
  return apiRequest<HarvestLot>(`/harvest-lots/${lotId}/revoke`, { method: 'POST' })
}

export function restoreHarvestLot(lotId: string) {
  return apiRequest<HarvestLot>(`/harvest-lots/${lotId}/restore`, { method: 'POST' })
}

export function getPublicPassport(token: string) {
  return apiRequest<PublicPassport>(`/public/passports/${token}`, { skipAuth: true, cache: 'no-store' })
}

export function publicPassportQrUrl(token: string) {
  return `${API_URL}/public/passports/${token}/qr.png`
}
