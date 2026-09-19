import { apiRequest } from '@/shared/lib/api'
import type { HealthStatus } from '@/shared/api/types'

export function getHealth() {
  return apiRequest<HealthStatus>('/health', { skipAuth: true })
}
