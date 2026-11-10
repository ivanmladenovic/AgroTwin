import type {
  PlanningItemStatus,
  PlanningPlanStatus,
  PlanningPlanType,
  PlanningScopeType,
  PlanningSeasonStatus,
} from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export const PLAN_TYPE_LABELS: Record<PlanningPlanType, string> = {
  get protection() {
    return tr('Zaštita')
  },
  get nutrition() {
    return tr('Ishrana')
  },
  get irrigation() {
    return tr('Navodnjavanje')
  },
}

export function seasonStatusLabel(status: PlanningSeasonStatus | string) {
  const map: Record<PlanningSeasonStatus, string> = {
    draft: tr('Nacrt'),
    active: tr('Aktivan'),
    completed: tr('Završen'),
    archived: tr('Arhiviran'),
  }
  return map[status as PlanningSeasonStatus] ?? status
}

export function planStatusLabel(status: PlanningPlanStatus | string) {
  const map: Record<PlanningPlanStatus, string> = {
    draft: tr('Nacrt'),
    ready_for_review: tr('Spremno za pregled'),
    expert_review: tr('Stručna provera'),
    approved: tr('Odobreno'),
    rejected: tr('Odbijeno'),
    active: tr('Aktivan'),
    completed: tr('Završen'),
  }
  return map[status as PlanningPlanStatus] ?? status
}

export function itemStatusLabel(status: PlanningItemStatus | string) {
  const map: Record<PlanningItemStatus, string> = {
    planned: tr('Planirano'),
    monitor: tr('Praćenje'),
    observed: tr('Zapaženo'),
    needs_review: tr('Za pregled'),
    approved: tr('Odobreno'),
    completed: tr('Završeno'),
    cancelled: tr('Otkazano'),
  }
  return map[status as PlanningItemStatus] ?? status
}

export function scopeLabel(scope: PlanningScopeType | string) {
  const map: Record<PlanningScopeType, string> = {
    parcel: tr('Ceo zasad'),
    row: tr('Red'),
    tree: tr('Sadnica'),
  }
  return map[scope as PlanningScopeType] ?? scope
}

export function semanticTypeLabel(value: string | null | undefined) {
  if (!value || value === 'other') return null
  const map: Record<string, string> = {
    observation: tr('zapažanje'),
    problem: tr('problem'),
    treatment: tr('tretman'),
    fertilization: tr('đubrenje'),
    irrigation: tr('navodnjavanje'),
    monitoring: tr('monitoring'),
    pruning: tr('rezidba'),
    planting: tr('sadnja'),
    other: tr('ostalo'),
  }
  return map[value] ?? value
}

export function observationStatusLabel(value: string | null | undefined) {
  if (!value) return null
  const map: Record<string, string> = {
    open: tr('otvoreno'),
    monitoring: tr('praćenje'),
    resolved: tr('rešeno'),
    unknown: tr('nepoznato'),
  }
  return map[value] ?? value
}
