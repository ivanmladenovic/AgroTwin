import type { ActivityStatus } from '@/shared/api/types'

export const activityStatuses: Array<{ value: ActivityStatus; label: string }> = [
  { value: 'planned', label: 'Planirano' },
  { value: 'in_progress', label: 'U toku' },
  { value: 'completed', label: 'Urađeno' },
  { value: 'cancelled', label: 'Otkazano' },
]

export function activityStatusLabel(value: string) {
  return activityStatuses.find((item) => item.value === value)?.label ?? value
}

export type CalendarKind = 'done' | 'planned' | 'overdue'

export function activityCalendarKind(status: string, performedOn: string, today: string): CalendarKind | null {
  if (status === 'cancelled') return null
  if (status === 'completed') return 'done'
  if (performedOn < today) return 'overdue'
  return 'planned'
}

export function defaultActivityStatus(performedOn: string, today: string): ActivityStatus {
  return performedOn > today ? 'planned' : 'completed'
}
