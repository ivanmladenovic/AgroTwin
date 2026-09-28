import { MapPinned, ShieldAlert, SquareStack, Trees } from 'lucide-react'
import type { ComponentType } from 'react'

import { meters } from '@/features/orchard/health'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import type { OrchardStats } from '@/shared/api/types'

export function ParcelSummary({ stats }: { stats: OrchardStats }) {
  const perRow = stats.trees_per_row ?? 0
  const missingCount = Math.max(stats.row_count * perRow - stats.active_trees, stats.removed_trees)
  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <StatCard
        label="Stabla"
        value={formatNumber(stats.active_trees)}
        detail={missingCount > 0 ? `${formatNumber(missingCount)} izostanak sadnice` : 'Aktivne sadnice'}
        icon={Trees}
      />
      <StatCard
        label="Redovi"
        value={formatNumber(stats.row_count)}
        detail={stats.trees_per_row ? `${formatNumber(stats.trees_per_row)} mesta po redu` : 'Redovi u zasadu'}
        icon={SquareStack}
      />
      <StatCard
        label="Površina"
        value={stats.area_hectares ? `${Number(stats.area_hectares).toFixed(2)} ha` : '—'}
        detail={`${meters(stats.row_spacing_m)} redovi · ${meters(stats.tree_spacing_m)} sadnice`}
        icon={MapPinned}
      />
      <StatCard
        label="Zdravlje"
        value={formatNumber(stats.issue_trees)}
        detail={`${formatNumber(stats.healthy_trees)} zdravo · ${formatNumber(stats.monitoring_trees)} praćenje`}
        icon={ShieldAlert}
        accent={stats.issue_trees > 0 ? 'warn' : 'ok'}
      />
    </div>
  )
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  accent = 'ok',
}: {
  label: string
  value: string
  detail: string
  icon: ComponentType<{ className?: string }>
  accent?: 'ok' | 'warn'
}) {
  return (
    <article className="rounded-xl border border-border bg-card p-4 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="mt-2 text-xl font-semibold tracking-tight sm:text-2xl">{value}</p>
        </div>
        <div className={cn('shrink-0 rounded-xl p-2.5 sm:p-3', accent === 'warn' ? 'bg-danger/10 text-danger' : 'bg-ok/10 text-ok')}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-2 truncate whitespace-nowrap text-xs font-medium text-muted-foreground" title={detail}>
        {detail}
      </p>
    </article>
  )
}
