import type { TreeHealthStatus, TreeStatus } from '@/shared/api/types'

export type OrchardTreeFilter = TreeHealthStatus | 'all' | 'missing' | 'attention'

export const orchardFilters: Array<{ value: OrchardTreeFilter; label: string }> = [
  { value: 'all', label: 'Sva stabla' },
  { value: 'healthy', label: 'Zdravo' },
  { value: 'monitoring', label: 'Praćenje' },
  { value: 'issue', label: 'Problem' },
  { value: 'attention', label: 'Zahtevaju pažnju' },
  { value: 'missing', label: 'Izostanak sadnice' },
]

export const healthFilters = orchardFilters

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

const healthLabels: Record<TreeHealthStatus, string> = {
  healthy: 'Zdravo',
  monitoring: 'Praćenje',
  issue: 'Problem',
  unknown: 'Nepoznato',
}

const statusLabels: Record<TreeStatus, string> = {
  active: 'Aktivno',
  removed: 'Uklonjeno',
  replaced: 'Zamenjeno',
}

export function healthLabel(health: TreeHealthStatus) {
  return healthLabels[health] ?? health
}

export function statusLabel(status: TreeStatus) {
  return statusLabels[status] ?? status
}

export function meters(value: string | number | null | undefined, digits = 1) {
  if (value === null || value === undefined || value === '') return '—'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(numeric)) return '—'
  return `${numeric.toFixed(digits)} m`
}
