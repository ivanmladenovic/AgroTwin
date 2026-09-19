import type { ParcelVariety } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'
import { formatNumber, rowLabel } from '@/shared/lib/format'
import { varietyColorMap } from '@/features/orchard/varieties'

export type PlantingPlan = {
  rowVarieties: string[]
  missing: Set<string>
}

export function gapKey(rowNumber: number, position: number) {
  return `${rowNumber}:${position}`
}

export function PlantingLayoutEditor({
  varieties,
  rowCount,
  treesPerRow,
  plan,
  selectedVariety,
  onSelectVariety,
  onChange,
}: {
  varieties: ParcelVariety[]
  rowCount: number
  treesPerRow: number
  plan: PlantingPlan
  selectedVariety: string
  onSelectVariety: (name: string) => void
  onChange: (plan: PlantingPlan) => void
}) {
  const colors = varietyColorMap(varieties)
  const totalSlots = rowCount * treesPerRow
  const planted = totalSlots - plan.missing.size
  const gap = treesPerRow > 80 ? 9 : 11
  const radius = gap * 0.38
  const width = treesPerRow * gap + 8
  const rowHeight = gap

  function paintRow(rowIndex: number) {
    const next = [...plan.rowVarieties]
    next[rowIndex] = selectedVariety
    onChange({ ...plan, rowVarieties: next })
  }

  function toggleGap(rowNumber: number, position: number) {
    const key = gapKey(rowNumber, position)
    const missing = new Set(plan.missing)
    if (missing.has(key)) missing.delete(key)
    else missing.add(key)
    onChange({ ...plan, missing })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {varieties.map((item) => (
          <button
            key={item.name}
            type="button"
            onClick={() => onSelectVariety(item.name)}
            className={cn(
              'flex items-center gap-2 border px-3 py-1.5 text-sm',
              selectedVariety === item.name ? 'border-primary bg-muted/70' : 'border-border hover:bg-muted/40',
            )}
          >
            <span className="h-3 w-3 rounded-full" style={{ background: item.color }} />
            {item.name}
          </button>
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Izaberite sortu, zatim kliknite broj reda da obojite red. Klik na sadnicu ostavlja prazno mesto.
      </p>
      <p className="font-mono text-xs text-muted-foreground">
        Ostaje {formatNumber(planted)} od {formatNumber(totalSlots)} sadnica
      </p>
      <div className="max-h-[32rem] overflow-auto border border-border bg-[var(--color-map-soil)] p-3">
        <div className="min-w-max space-y-0">
          {Array.from({ length: rowCount }, (_, rowIndex) => {
            const rowNumber = rowIndex + 1
            const variety = plan.rowVarieties[rowIndex]
            const color = colors.get(variety) ?? '#DC2626'
            return (
              <div key={rowNumber} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => paintRow(rowIndex)}
                  className="w-10 shrink-0 text-left font-mono text-[11px] text-muted-foreground hover:text-foreground"
                >
                  {rowLabel(rowNumber)}
                </button>
                <svg width={width} height={rowHeight} className="block">
                  {Array.from({ length: treesPerRow }, (_, posIndex) => {
                    const position = posIndex + 1
                    const missing = plan.missing.has(gapKey(rowNumber, position))
                    return (
                      <circle
                        key={position}
                        cx={4 + posIndex * gap}
                        cy={rowHeight / 2}
                        r={radius}
                        role="button"
                        tabIndex={0}
                        aria-label={
                          missing
                            ? `Praznina na redu ${rowNumber}, pozicija ${position}`
                            : `${variety} na redu ${rowNumber}, pozicija ${position}`
                        }
                        fill={missing ? 'transparent' : color}
                        stroke={missing ? '#7a7468' : color}
                        strokeDasharray={missing ? '2 2' : undefined}
                        style={{ cursor: 'pointer' }}
                        onClick={() => toggleGap(rowNumber, position)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            toggleGap(rowNumber, position)
                          }
                        }}
                      />
                    )
                  })}
                </svg>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
