import { apiRequest } from '@/shared/lib/api'
import type { Farm, FarmDetail } from '@/shared/api/types'

export function listFarms() {
  return apiRequest<Farm[]>('/farms')
}

export function getFarm(farmId: string) {
  return apiRequest<FarmDetail>(`/farms/${farmId}`)
}
