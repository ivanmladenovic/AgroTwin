import type { TreeHealthStatus, TreeStatus } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export type OrchardTreeFilter = TreeHealthStatus | 'all' | 'missing' | 'attention'

export function getOrchardFilters(): Array<{ value: OrchardTreeFilter; label: string }> {
  return [
    { value: 'all', label: tr('Sva stabla') },
    { value: 'healthy', label: tr('Zdravo') },
    { value: 'monitoring', label: tr('Praćenje') },
    { value: 'issue', label: tr('Problem') },
    { value: 'attention', label: tr('Zahtevaju pažnju') },
    { value: 'missing', label: tr('Izostanak sadnice') },
  ]
}

/** @deprecated Use getOrchardFilters() for translated labels */
export const orchardFilters = getOrchardFilters()

export const healthFilters = getOrchardFilters

export function treeMarkerClass(
  status: TreeStatus,
  health: TreeHealthStatus,
  hasSevereCase = false,
) {
  if (status === 'removed') return 'tree-status-removed'
  if (status === 'replaced') return 'tree-status-replaced'
  if (hasSevereCase) return 'tree-health-issue tree-health-severe'
  return `tree-health-${health}`
}

export function healthLabel(health: TreeHealthStatus) {
  const healthLabels: Record<TreeHealthStatus, string> = {
    healthy: tr('Zdravo'),
    monitoring: tr('Praćenje'),
    issue: tr('Problem'),
    unknown: tr('Nepoznato'),
  }
  return healthLabels[health] ?? health
}

export function statusLabel(status: TreeStatus) {
  const statusLabels: Record<TreeStatus, string> = {
    active: tr('Aktivno'),
    removed: tr('Uklonjeno'),
    replaced: tr('Zamenjeno'),
  }
  return statusLabels[status] ?? status
}

export function meters(value: string | number | null | undefined, digits = 1) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  return `${numeric.toFixed(digits)} m`
}
