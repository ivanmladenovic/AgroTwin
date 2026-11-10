import type { ActivityStatus } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export function activityStatuses(): Array<{ value: ActivityStatus; label: string }> {
  return [
    { value: 'planned', label: tr('Planirano') },
    { value: 'in_progress', label: tr('U toku') },
    { value: 'completed', label: tr('Urađeno') },
    { value: 'cancelled', label: tr('Otkazano') },
  ]
}

export function activityStatusLabel(value: string) {
  return activityStatuses().find((item) => item.value === value)?.label ?? value
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
