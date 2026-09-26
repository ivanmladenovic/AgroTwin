import { apiRequest } from '@/shared/lib/api'
import type { OrchardSeason, OrchardSeasonPayload, TaskSchedule, TaskSchedulePayload } from '@/shared/api/types'

export function listSeasons(parcelId?: string) {
  const query = parcelId ? `?parcel_id=${parcelId}` : ''
  return apiRequest<OrchardSeason[]>(`/seasons${query}`)
}

export function createSeason(payload: OrchardSeasonPayload) {
  return apiRequest<OrchardSeason>('/seasons', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteSeason(seasonId: string) {
  return apiRequest<void>(`/seasons/${seasonId}`, { method: 'DELETE' })
}

export function listSchedules(parcelId?: string) {
  const query = parcelId ? `?parcel_id=${parcelId}` : ''
  return apiRequest<TaskSchedule[]>(`/schedules${query}`)
}

export function createSchedule(payload: TaskSchedulePayload) {
  return apiRequest<TaskSchedule>('/schedules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteSchedule(scheduleId: string) {
  return apiRequest<void>(`/schedules/${scheduleId}`, { method: 'DELETE' })
}
