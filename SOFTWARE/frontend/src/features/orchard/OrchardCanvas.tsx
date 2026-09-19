import { useEffect, useMemo, useRef, useState } from 'react'

import { treeMarkerClass, type OrchardTreeFilter } from '@/features/orchard/health'
import { varietyColorMap, varietiesFromTwin } from '@/features/orchard/varieties'
import type { OrchardTwin, TreeMapItem } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'

type ViewBox = { x: number; y: number; w: number; h: number }

type OrchardCanvasProps = {
  twin: OrchardTwin
  selectedTreeId: string | null
  healthFilter?: OrchardTreeFilter
  onSelectTree?: (treeId: string) => void
  pickMode?: 'tree' | 'rows'
  selectedRowIds?: string[]
  onToggleRow?: (rowId: string) => void
}

function fitView(twin: OrchardTwin): ViewBox {
  const width = Number(twin.width_m)
  const height = Number(twin.height_m)
  const padX = Math.max(6, width * 0.1)
  const padY = Math.max(8, height * 0.14)
  return { x: -padX, y: -padY, w: width + padX * 2, h: height + padY * 2 }
}

export function OrchardCanvas({
  twin,
  selectedTreeId,
  healthFilter = 'all',
  onSelectTree,
  pickMode,
  selectedRowIds = [],
  onToggleRow,
}: OrchardCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; y: number; view: ViewBox } | null>(null)
  const fitted = useMemo(() => fitView(twin), [twin])
  const [view, setView] = useState<ViewBox>(fitted)

  useEffect(() => {
    setView(fitted)
  }, [fitted])

  const rowSpacing = Number(twin.parcel.row_spacing_m ?? 5)
  const treeSpacing = Number(twin.parcel.tree_spacing_m ?? 3.5)
  const radius = Math.min(rowSpacing, treeSpacing) * 0.18
  const colors = varietyColorMap(twin.parcel.varieties)
  const varieties = varietiesFromTwin(twin)
  const gaps = useMemo(() => missingSlots(twin, rowSpacing, treeSpacing), [twin, rowSpacing, treeSpacing])
  const selectedRows = useMemo(() => new Set(selectedRowIds), [selectedRowIds])

  function handleTreeSelect(tree: TreeMapItem) {
    if (pickMode === 'rows') {
      onToggleRow?.(tree.row_id)
      return
    }
    onSelectTree?.(tree.id)
  }

  function treeVisibility(tree: TreeMapItem) {
    const missing = tree.status === 'removed'
    if (healthFilter === 'all') return { dimmed: false, faint: missing }
    if (healthFilter === 'missing') return { dimmed: !missing, faint: false }
    if (healthFilter === 'attention') {
      const needsAttention = tree.health_status === 'issue' || tree.health_status === 'monitoring'
      return { dimmed: missing || !needsAttention, faint: false }
    }
    return { dimmed: missing || tree.health_status !== healthFilter, faint: false }
  }

  const gapsDimmed = healthFilter !== 'all' && healthFilter !== 'missing'
  const gapsFaint = healthFilter === 'all'

  function clientToView(event: { clientX: number; clientY: number }): { x: number; y: number } | null {
    const svg = svgRef.current
    if (!svg) return null
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const ctm = svg.getScreenCTM()
    if (!ctm) return null
    const mapped = point.matrixTransform(ctm.inverse())
    return { x: mapped.x, y: mapped.y }
  }

  function zoom(factor: number, origin?: { x: number; y: number }) {
    const cx = origin?.x ?? view.x + view.w / 2
    const cy = origin?.y ?? view.y + view.h / 2
    const next = {
      w: view.w * factor,
      h: view.h * factor,
      x: cx - (cx - view.x) * factor,
      y: cy - (cy - view.y) * factor,
    }
    setView(next)
  }

  return (
    <div className="relative h-full min-h-[min(52dvh,28rem)] overflow-hidden bg-[var(--color-map-soil)] lg:min-h-[min(70vh,40rem)]">
      <svg
        ref={svgRef}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        onWheel={(event) => {
          event.preventDefault()
          const origin = clientToView(event)
          zoom(event.deltaY > 0 ? 1.12 : 0.88, origin ?? undefined)
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return
          const target = event.target as Element
          if (target.closest('[role="button"]')) return
          drag.current = { x: event.clientX, y: event.clientY, view }
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerMove={(event) => {
          if (!drag.current || !svgRef.current) return
          const svg = svgRef.current
          const dx = ((event.clientX - drag.current.x) / svg.clientWidth) * drag.current.view.w
          const dy = ((event.clientY - drag.current.y) / svg.clientHeight) * drag.current.view.h
          setView({
            ...drag.current.view,
            x: drag.current.view.x - dx,
            y: drag.current.view.y - dy,
          })
        }}
        onPointerUp={() => {
          drag.current = null
        }}
      >
        <g>
          {twin.rows.map((row) => {
            const y = (row.row_number - 1) * rowSpacing
            const selected = selectedRows.has(row.id)
            const dimRow = selectedRows.size > 0 && !selected
            return (
              <rect
                key={row.id}
                role={pickMode === 'rows' ? 'button' : undefined}
                aria-label={pickMode === 'rows' ? `Red ${String(row.row_number).padStart(2, '0')}` : undefined}
                x={-treeSpacing * 0.45}
                y={y - rowSpacing * 0.5}
                width={Number(twin.width_m) + treeSpacing * 0.9}
                height={rowSpacing}
                className={cn(
                  row.row_number % 2 === 0 ? 'fill-[var(--color-map-row-even)]' : 'fill-[var(--color-map-row-odd)]',
                  selected && 'stroke-primary',
                  dimRow && 'opacity-35',
                )}
                strokeWidth={selected ? rowSpacing * 0.08 : 0}
                style={{ cursor: pickMode === 'rows' ? 'pointer' : undefined }}
                onClick={(event) => {
                  if (pickMode !== 'rows') return
                  event.stopPropagation()
                  onToggleRow?.(row.id)
                }}
              />
            )
          })}
          {twin.rows.map((row) => {
            const y = (row.row_number - 1) * rowSpacing
            return (
              <text
                key={`label-${row.id}`}
                x={-treeSpacing * 0.7}
                y={y + radius * 0.35}
                textAnchor="end"
                className="fill-foreground/70"
                style={{ fontSize: Math.max(rowSpacing * 0.28, 1.1), fontFamily: 'Montserrat, sans-serif', fontWeight: 600 }}
              >
                {String(row.row_number).padStart(2, '0')}
              </text>
            )
          })}
          {twin.trees
            .filter((tree) => tree.status !== 'removed')
            .map((tree) => {
            const visibility = treeVisibility(tree)
            return (
              <TreeDot
                key={tree.id}
                tree={tree}
                radius={radius}
                color={tree.variety ? colors.get(tree.variety) : undefined}
                selected={tree.id === selectedTreeId}
                dimmed={pickMode === 'rows' ? false : visibility.dimmed}
                faint={visibility.faint}
                onSelect={() => handleTreeSelect(tree)}
              />
            )
          })}
          {gaps.map((gap) => (
            <MissingDot
              key={gap.key}
              x={gap.x}
              y={gap.y}
              radius={radius}
              dimmed={gapsDimmed}
              faint={gapsFaint}
            />
          ))}
        </g>
      </svg>

      <div className="absolute left-4 top-4 flex gap-1">
        <MapButton label="+" onClick={() => zoom(0.8)} />
        <MapButton label="−" onClick={() => zoom(1.25)} />
        <MapButton label="Početni prikaz" onClick={() => setView(fitted)} />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-3">
        <div className="pointer-events-auto inline-flex max-w-full flex-wrap gap-2 rounded-xl border border-border/70 bg-card/95 px-3 py-2 text-xs shadow-md">
          {varieties.map((item) => (
            <span key={item.name} className="inline-flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
              <span>{item.name}</span>
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <span className="h-2.5 w-2.5 rounded-full border border-dashed border-muted-foreground bg-transparent" />
            Izostanak sadnice
          </span>
        </div>
      </div>
    </div>
  )
}

function TreeDot({
  tree,
  radius,
  color,
  selected,
  dimmed,
  faint,
  onSelect,
}: {
  tree: TreeMapItem
  radius: number
  color?: string
  selected: boolean
  dimmed: boolean
  faint: boolean
  onSelect: () => void
}) {
  const x = Number(tree.normalized_x)
  const y = Number(tree.normalized_y)
  const missing = tree.status === 'removed'
  const healthClass = treeMarkerClass(tree.status, tree.health_status, Boolean(tree.has_severe_case))
  const useVarietyColor = Boolean(color) && tree.status === 'active'
  return (
    <g
      role="button"
      aria-label={tree.public_id}
      className={cn(dimmed && 'opacity-20', faint && 'opacity-50')}
      style={{ pointerEvents: dimmed ? 'none' : 'auto', cursor: 'pointer' }}
      onClick={(event) => {
        event.stopPropagation()
        onSelect()
      }}
    >
      {selected ? (
        <circle cx={x} cy={y} r={radius * 1.85} className="fill-none stroke-foreground" strokeWidth={radius * 0.28} />
      ) : null}
      {tree.has_severe_case && tree.status === 'active' ? (
        <circle cx={x} cy={y} r={radius * 1.55} className="tree-severe-ring" />
      ) : null}
      <circle
        cx={x}
        cy={y}
        r={radius}
        className={useVarietyColor ? undefined : healthClass}
        style={useVarietyColor ? { fill: color } : undefined}
        strokeDasharray={missing ? `${radius * 0.55} ${radius * 0.4}` : undefined}
      />
    </g>
  )
}

function missingSlots(twin: OrchardTwin, rowSpacing: number, treeSpacing: number) {
  const occupied = new Set(
    twin.trees
      .filter((tree) => tree.status !== 'removed')
      .map((tree) => `${tree.row_number}-${tree.position_in_row}`),
  )
  const rowCount = twin.stats.row_count
  const perRow = twin.stats.trees_per_row ?? twin.parcel.trees_per_row ?? 0
  const slots: Array<{ key: string; x: number; y: number }> = []
  for (let row = 1; row <= rowCount; row += 1) {
    for (let position = 1; position <= perRow; position += 1) {
      if (occupied.has(`${row}-${position}`)) continue
      slots.push({
        key: `gap-${row}-${position}`,
        x: (position - 1) * treeSpacing,
        y: (row - 1) * rowSpacing,
      })
    }
  }
  return slots
}

function MissingDot({
  x,
  y,
  radius,
  dimmed,
  faint,
}: {
  x: number
  y: number
  radius: number
  dimmed: boolean
  faint: boolean
}) {
  return (
    <circle
      cx={x}
      cy={y}
      r={radius}
      className={cn('tree-status-removed', dimmed && 'opacity-20', faint && 'opacity-50')}
      strokeDasharray={`${radius * 0.55} ${radius * 0.4}`}
    />
  )
}

function MapButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-11 min-w-11 items-center justify-center border border-border bg-card px-3 text-sm font-medium hover:bg-muted lg:h-8 lg:min-w-8 lg:px-2 lg:text-xs"
    >
      {label}
    </button>
  )
}
