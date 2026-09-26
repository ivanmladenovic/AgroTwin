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
import type { ReportProblemValues } from '@/features/health/schemas'

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

export async function saveReportedProblem(values: ReportProblemValues, files: File[]) {
  const treeIds =
    values.scope === 'trees'
      ? values.tree_ids ?? []
      : values.scope === 'tree' && values.tree_id
        ? [values.tree_id]
        : []
  const created = await createDiseaseCase({
    parcel_id: values.parcel_id,
    row_id: values.row_id || null,
    tree_id: values.scope === 'tree' ? values.tree_id || null : null,
    tree_ids: treeIds,
    detected_on: values.detected_on,
    status: values.status,
    category: values.category,
    title: values.title,
    description: values.description || null,
    severity: values.severity,
    notes: values.notes || null,
    symptoms: values.symptoms || (files.length ? 'Uz prijavu je priložena fotografija.' : null),
  })
  const observationId = created.observations[0]?.id
  if (observationId) {
    for (const file of files) {
      await uploadPhoto(file, 'observation', observationId)
    }
  }
  return created
}

export function uploadPhoto(file: File, entityType: string, entityId: string, caption?: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('entity_type', entityType)
  form.append('entity_id', entityId)
  if (caption) form.append('caption', caption)
  return apiUpload<PhotoRecord>('/photos', form)
}
