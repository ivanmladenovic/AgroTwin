import { Link } from 'react-router-dom'

import { healthLabel, statusLabel } from '@/features/orchard/health'
import type { TreeDetail } from '@/shared/api/types'
import { formatMoney, rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'

export function TreeDrawer({
  tree,
  parcelId,
  onClose,
}: {
  tree: TreeDetail
  parcelId: string
  onClose: () => void
}) {
  const fields = [
    { label: 'ID stabla', value: tree.public_id },
    { label: 'Red', value: rowLabel(tree.row_number) },
    { label: 'Pozicija', value: String(tree.position_in_row) },
    { label: 'Sorta', value: tree.variety ?? '—' },
    { label: 'Godina sadnje', value: tree.planting_year ? String(tree.planting_year) : '—' },
    { label: 'Stanje', value: statusLabel(tree.status) },
    { label: 'Zdravlje', value: healthLabel(tree.health_status) },
    { label: 'Aktivnosti', value: String(tree.activity_count) },
    { label: 'Problemi', value: String(tree.disease_issue_count) },
    { label: 'Ukupan trošak', value: formatMoney(tree.total_cost) },
  ]

  return (
    <div className="flex h-full flex-col border-border bg-card lg:border-l">
      <div className="flex items-start justify-between border-b border-border px-4 py-3">
        <div>
          <p className="kicker">Stablo</p>
          <h2 className="mt-1 font-mono text-lg">{tree.public_id}</h2>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Zatvori
        </Button>
      </div>
      <dl className="flex-1 space-y-3 overflow-auto px-4 py-4">
        {fields.map((field) => (
          <div key={field.label}>
            <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{field.label}</dt>
            <dd className="mt-1 text-sm">{field.value}</dd>
          </div>
        ))}
      </dl>
      <div className="space-y-2 border-t border-border px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <Link
          to={`/health/new?parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}`}
          className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-primary text-sm text-primary-foreground hover:bg-primary/90 lg:h-10"
        >
          + Prijavi problem
        </Link>
        <Link
          to={`/activities/new?scope=tree&parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}`}
          className="inline-flex h-11 w-full items-center justify-center rounded-lg border border-border text-sm hover:bg-muted lg:h-10"
        >
          + Dodaj aktivnost
        </Link>
        <Link
          to={`/orchard/${parcelId}/trees/${tree.id}`}
          className="inline-flex h-11 w-full items-center justify-center rounded-lg border border-border text-sm hover:bg-muted lg:h-10"
        >
          Otvori dnevnik stabla
        </Link>
      </div>
    </div>
  )
}
