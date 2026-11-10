import { apiRequest } from '@/shared/lib/api'
import type {
  CatalogItem,
  ParcelLaborSummary,
  WorkTask,
  WorkTaskCreatePayload,
  WorkTaskFilters,
  WorkTaskUpdatePayload,
  Worker,
  WorkerCreatePayload,
  WorkerUpdatePayload,
  WorkforceDashboard,
} from '@/shared/api/types'

function queryString(filters: Record<string, string | boolean | undefined | null> = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export function listWorkTaskTypes() {
  return apiRequest<CatalogItem[]>('/work-task-types')
}

export function listWorkers(activeOnly = false) {
  return apiRequest<Worker[]>(`/workers${queryString({ active_only: activeOnly || undefined })}`)
}

export function createWorker(payload: WorkerCreatePayload) {
  return apiRequest<Worker>('/workers', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateWorker(workerId: string, payload: WorkerUpdatePayload) {
  return apiRequest<Worker>(`/workers/${workerId}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function deleteWorker(workerId: string) {
  return apiRequest<void>(`/workers/${workerId}`, { method: 'DELETE' })
}

export function listWorkTasks(filters: WorkTaskFilters = {}) {
  return apiRequest<WorkTask[]>(`/work-tasks${queryString(filters)}`)
}

export function createWorkTask(payload: WorkTaskCreatePayload) {
  return apiRequest<WorkTask>('/work-tasks', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateWorkTask(taskId: string, payload: WorkTaskUpdatePayload) {
  return apiRequest<WorkTask>(`/work-tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(payload) })
}

export function deleteWorkTask(taskId: string) {
  return apiRequest<void>(`/work-tasks/${taskId}`, { method: 'DELETE' })
}

export function getWorkforceDashboard(filters: WorkTaskFilters = {}) {
  return apiRequest<WorkforceDashboard>(`/workforce/dashboard${queryString(filters)}`)
}

export function getParcelLabor(parcelId: string) {
  return apiRequest<ParcelLaborSummary>(`/parcels/${parcelId}/labor`)
}
