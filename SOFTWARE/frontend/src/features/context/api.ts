import { apiRequest } from '@/shared/lib/api'
import type { AgroTwinContext, ContextBuildRequest } from '@/shared/api/types'

export function buildContext(payload: ContextBuildRequest) {
  return apiRequest<AgroTwinContext>('/context/build', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function previewContext(payload: ContextBuildRequest) {
  return apiRequest<AgroTwinContext>('/context/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
