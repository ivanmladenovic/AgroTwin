import { apiRequest, apiUpload } from '@/shared/lib/api'
import type {
  DiseaseCase,
  DiseaseCaseCreatePayload,
  DiseaseCaseDetail,
  DiseaseCaseUpdatePayload,
  DiseaseCategory,
  DiseaseStatus,
  Observation,
  ObservationCreatePayload,
  PhotoRecord,
} from '@/shared/api/types'

export function listDiseaseCases(filters: {
  parcel_id?: string
  tree_id?: string
  status?: DiseaseStatus | ''
  category?: DiseaseCategory | ''
} = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value)
  }
  const query = params.toString()
  return apiRequest<DiseaseCase[]>(`/disease-cases${query ? `?${query}` : ''}`)
}

export function getDiseaseCase(caseId: string) {
  return apiRequest<DiseaseCaseDetail>(`/disease-cases/${caseId}`)
}

export function createDiseaseCase(payload: DiseaseCaseCreatePayload) {
  return apiRequest<DiseaseCaseDetail>('/disease-cases', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDiseaseCase(caseId: string, payload: DiseaseCaseUpdatePayload) {
  return apiRequest<DiseaseCaseDetail>(`/disease-cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function addObservation(caseId: string, payload: ObservationCreatePayload) {
  return apiRequest<Observation>(`/disease-cases/${caseId}/observations`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function uploadPhoto(file: File, entityType: string, entityId: string, caption?: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('entity_type', entityType)
  form.append('entity_id', entityId)
  if (caption) form.append('caption', caption)
  return apiUpload<PhotoRecord>('/photos', form)
}
