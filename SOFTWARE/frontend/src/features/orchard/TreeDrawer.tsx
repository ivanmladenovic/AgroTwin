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
    { label: 'ID', value: tree.public_id },
    { label: 'Red', value: rowLabel(tree.row_number) },
    { label: 'Poz.', value: String(tree.position_in_row) },
    { label: 'Sorta', value: tree.variety ?? '—' },
    { label: 'Sadnja', value: tree.planting_year ? String(tree.planting_year) : '—' },
    { label: 'Stanje', value: statusLabel(tree.status) },
    { label: 'Zdravlje', value: healthLabel(tree.health_status) },
    { label: 'Aktivnosti', value: String(tree.activity_count) },
    { label: 'Problemi', value: String(tree.disease_issue_count) },
    { label: 'Trošak', value: formatMoney(tree.total_cost) },
  ]

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <div className="flex shrink-0 items-start justify-between gap-2 border-b border-border px-2.5 py-2 lg:px-4 lg:py-2.5">
        <div className="min-w-0">
          <p className="kicker text-[10px] lg:text-xs">Stablo</p>
          <h2 className="mt-0.5 truncate font-mono text-sm lg:text-base">{tree.public_id}</h2>
        </div>
        <Button variant="ghost" size="sm" className="h-8 shrink-0 px-2 text-xs lg:h-10 lg:px-3" onClick={onClose}>
          Zatvori
        </Button>
      </div>

      <dl className="grid min-h-0 flex-1 grid-cols-2 content-start gap-x-2 gap-y-1.5 overflow-auto px-2.5 py-2 lg:gap-x-4 lg:gap-y-2.5 lg:px-4 lg:py-3">
        {fields.map((field) => (
          <div key={field.label} className="min-w-0">
            <dt className="truncate text-[10px] leading-none text-muted-foreground lg:text-[11px]">{field.label}</dt>
            <dd className="mt-0.5 truncate text-xs font-medium lg:text-sm" title={field.value}>
              {field.value}
            </dd>
          </div>
        ))}
      </dl>

      <div className="shrink-0 space-y-1.5 border-t border-border px-2.5 py-2 lg:space-y-2 lg:px-4 lg:py-3 lg:pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <Link
          to={`/health/new?parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}`}
          className="inline-flex h-8 w-full items-center justify-center rounded-md bg-primary px-1 text-center text-[11px] font-semibold leading-tight text-primary-foreground hover:bg-primary/90 lg:h-10 lg:rounded-lg lg:text-sm"
        >
          + Prijavi problem
        </Link>
        <Link
          to={`/activities/new?scope=tree&parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}`}
          className="inline-flex h-8 w-full items-center justify-center rounded-md border border-border px-1 text-center text-[11px] font-semibold leading-tight hover:bg-muted lg:h-10 lg:rounded-lg lg:text-sm"
        >
          + Dodaj aktivnost
        </Link>
        <Link
          to={`/orchard/${parcelId}/trees/${tree.id}`}
          className="inline-flex h-8 w-full items-center justify-center rounded-md border border-border px-1 text-center text-[11px] font-semibold leading-tight hover:bg-muted lg:h-10 lg:rounded-lg lg:text-sm"
        >
          Dnevnik stabla
        </Link>
      </div>
    </div>
  )
}
