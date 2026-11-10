import { MapPinned, ShieldAlert, SquareStack, Trees } from 'lucide-react'
import type { ComponentType } from 'react'

import { meters } from '@/features/orchard/health'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import type { OrchardStats, ParcelVariety } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export function ParcelSummary({
  stats,
  varieties,
  plantingYear,
  compact = false,
}: {
  stats: OrchardStats
  varieties?: ParcelVariety[]
  plantingYear?: number | null
  compact?: boolean
}) {
  const perRow = stats.trees_per_row ?? 0
  const missingCount = Math.max(stats.row_count * perRow - stats.active_trees, stats.removed_trees)
  return (
    <div className="space-y-3">
      <div className={cn('grid grid-cols-2 gap-3', compact ? 'xl:grid-cols-4' : 'xl:grid-cols-4')}>
        <StatCard
          label={tr('Stabla')}
          value={formatNumber(stats.active_trees)}
          detail={
            missingCount > 0
              ? tr('{{count}} izostanak sadnice', { count: formatNumber(missingCount) })
              : tr('Aktivne sadnice')
          }
          icon={Trees}
          compact={compact}
        />
        <StatCard
          label={tr('Redovi')}
          value={formatNumber(stats.row_count)}
          detail={
            stats.trees_per_row
              ? tr('do {{count}}/red', { count: formatNumber(stats.trees_per_row) })
              : tr('Redovi u zasadu')
          }
          icon={SquareStack}
          compact={compact}
        />
        <StatCard
          label={tr('Površina')}
          value={stats.area_hectares ? `${Number(stats.area_hectares).toFixed(2)} ha` : '—'}
          detail={
            plantingYear
              ? tr('sadnja {{year}}', { year: plantingYear })
              : tr('{{rowSpacing}} redovi · {{treeSpacing}} sadnice', {
                  rowSpacing: meters(stats.row_spacing_m),
                  treeSpacing: meters(stats.tree_spacing_m),
                })
          }
          icon={MapPinned}
          compact={compact}
        />
        <StatCard
          label={tr('Zdravlje')}
          value={formatNumber(stats.issue_trees)}
          detail={tr('{{healthy}} zdravo · {{monitoring}} praćenje', {
            healthy: formatNumber(stats.healthy_trees),
            monitoring: formatNumber(stats.monitoring_trees),
          })}
          icon={ShieldAlert}
          accent={stats.issue_trees > 0 ? 'warn' : 'ok'}
          compact={compact}
        />
      </div>
      {varieties && varieties.length > 0 ? (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 px-0.5 text-xs text-muted-foreground">
          {varieties.map((item) => (
            <span key={item.name} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
              {item.name}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  accent = 'ok',
  compact = false,
}: {
  label: string
  value: string
  detail: string
  icon: ComponentType<{ className?: string }>
  accent?: 'ok' | 'warn'
  compact?: boolean
}) {
  return (
    <article className={cn('rounded-xl border border-border bg-card', compact ? 'p-3 sm:p-4' : 'p-4 sm:p-5')}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className={cn('mt-1.5 font-semibold tracking-tight', compact ? 'text-lg sm:text-xl' : 'mt-2 text-xl sm:text-2xl')}>
            {value}
          </p>
        </div>
        <div
          className={cn(
            'shrink-0 rounded-xl p-2 sm:p-2.5',
            accent === 'warn' ? 'bg-danger/10 text-danger' : 'bg-ok/10 text-ok',
          )}
        >
          <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
        </div>
      </div>
      <p className="mt-1.5 truncate whitespace-nowrap text-xs font-medium text-muted-foreground" title={detail}>
        {detail}
      </p>
    </article>
  )
}
