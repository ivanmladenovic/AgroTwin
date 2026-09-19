import { apiRequest } from '@/shared/lib/api'
import type { DashboardOverview } from '@/shared/api/types'

export function getDashboard() {
  return apiRequest<DashboardOverview>('/dashboard')
}
