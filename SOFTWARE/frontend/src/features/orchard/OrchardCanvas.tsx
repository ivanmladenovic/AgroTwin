import { useEffect, useMemo, useRef, useState } from 'react'

import { treeMarkerClass, type OrchardTreeFilter } from '@/features/orchard/health'
import { varietyColorMap, varietiesFromTwin } from '@/features/orchard/varieties'
import type { OrchardTwin, TreeMapItem } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'
import { tr } from '@/shared/i18n/i18n'

type ViewBox = { x: number; y: number; w: number; h: number }

type OrchardCanvasProps = {
  twin: OrchardTwin
  selectedTreeId: string | null
  healthFilter?: OrchardTreeFilter
  onSelectTree?: (treeId: string) => void
  pickMode?: 'tree' | 'rows' | 'trees'
  selectedRowIds?: string[]
  selectedTreeIds?: string[]
  onToggleRow?: (rowId: string) => void
  /** When set, pan the map so this tree stays visible (used after arrow navigation). */
  focusTreeId?: string | null
  showLegend?: boolean
}

/** Schematic grid size from planting layout only (ignore geo width_m/height_m). */
function schematicSize(twin: OrchardTwin) {
  const rowSpacing = Number(twin.parcel.row_spacing_m ?? 5)
  const treeSpacing = Number(twin.parcel.tree_spacing_m ?? 3.5)
  const rowCount = Math.max(
    twin.stats.row_count,
    twin.rows.length,
    ...twin.trees.map((tree) => tree.row_number),
    1,
  )
  const perRow = Math.max(
    twin.stats.trees_per_row ?? twin.parcel.trees_per_row ?? 0,
    ...twin.trees.map((tree) => tree.position_in_row),
    1,
  )
  return {
    width: Math.max((perRow - 1) * treeSpacing, treeSpacing),
    height: Math.max((rowCount - 1) * rowSpacing, rowSpacing),
    rowSpacing,
    treeSpacing,
  }
}

function schematicXY(tree: Pick<TreeMapItem, 'row_number' | 'position_in_row'>, rowSpacing: number, treeSpacing: number) {
  return {
    x: (tree.position_in_row - 1) * treeSpacing,
    y: (tree.row_number - 1) * rowSpacing,
  }
}

/**
 * Fit the tree grid into the SVG viewport, centered.
 * Target fill ≈ one "+" click from a tight fit (~75% of the limiting axis).
 */
function fitView(twin: OrchardTwin, containerAspect = 1): ViewBox {
  const { width, height, rowSpacing, treeSpacing } = schematicSize(twin)
  // Half-row stripe + room for row number labels on the left.
  const x0 = -treeSpacing * 0.72
  const y0 = -rowSpacing * 0.5
  const x1 = width + treeSpacing * 0.35
  const y1 = height + rowSpacing * 0.5
  const contentW = Math.max(x1 - x0, treeSpacing)
  const contentH = Math.max(y1 - y0, rowSpacing)
  const cx = (x0 + x1) / 2
  const cy = (y0 + y1) / 2
  // Same visual scale as pressing "+" once on a tight fit (zoom factor 0.8).
  const targetFill = 0.8
  let viewW = contentW / targetFill
  let viewH = contentH / targetFill
  const aspect = containerAspect > 0.2 && Number.isFinite(containerAspect) ? containerAspect : viewW / viewH

  if (aspect >= viewW / viewH) {
    viewW = viewH * aspect
  } else {
    viewH = viewW / aspect
  }
  return {
    x: cx - viewW / 2,
    y: cy - viewH / 2,
    w: viewW,
    h: viewH,
  }
}

export function OrchardCanvas({
  twin,
  selectedTreeId,
  healthFilter = 'all',
  onSelectTree,
  pickMode,
  selectedRowIds = [],
  selectedTreeIds = [],
  onToggleRow,
  focusTreeId = null,
  showLegend = true,
}: OrchardCanvasProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ x: number; y: number; view: ViewBox } | null>(null)
  const [containerAspect, setContainerAspect] = useState(1)
  const fitted = useMemo(() => fitView(twin, containerAspect), [twin, containerAspect])
  const [view, setView] = useState<ViewBox>(fitted)
  const userAdjustedView = useRef(false)
  const lastFocusedTreeId = useRef<string | null>(null)

  useEffect(() => {
    const node = rootRef.current
    if (!node) return
    function measure() {
      const rect = node.getBoundingClientRect()
      if (rect.width < 2 || rect.height < 2) return
      setContainerAspect(rect.width / rect.height)
    }
    measure()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    observer?.observe(node)
    return () => observer?.disconnect()
  }, [])

  useEffect(() => {
    userAdjustedView.current = false
  }, [twin.parcel.id])

  useEffect(() => {
    // Re-fit when twin or container aspect changes, unless the user already panned/zoomed.
    if (userAdjustedView.current) return
    setView(fitted)
  }, [fitted])

  const { rowSpacing, treeSpacing, width: plotWidth } = useMemo(() => schematicSize(twin), [twin])

  useEffect(() => {
    if (!focusTreeId) {
      lastFocusedTreeId.current = null
      return
    }
    if (focusTreeId === lastFocusedTreeId.current) return
    const tree = twin.trees.find((item) => item.id === focusTreeId)
    if (!tree) return
    lastFocusedTreeId.current = focusTreeId
    const { x: tx, y: ty } = schematicXY(tree, rowSpacing, treeSpacing)
    setView((current) => ({
      ...current,
      // Keep selection left of the mobile side panel / desktop drawer.
      x: tx - current.w * 0.38,
      y: ty - current.h * 0.5,
    }))
  }, [focusTreeId, twin.trees, rowSpacing, treeSpacing])

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
    userAdjustedView.current = true
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

  function resetView() {
    userAdjustedView.current = false
    setView(fitView(twin, containerAspect))
  }

  return (
    <div ref={rootRef} className="relative h-full min-h-0 w-full overflow-hidden bg-[var(--color-map-soil)]">
      <svg
        ref={svgRef}
        className="h-full w-full touch-none cursor-grab active:cursor-grabbing"
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        preserveAspectRatio="xMidYMid meet"
        onWheel={(event) => {
          event.preventDefault()
          const origin = clientToView(event)
          zoom(event.deltaY > 0 ? 1.12 : 0.88, origin ?? undefined)
        }}
        onPointerDown={(event) => {
          if (event.button !== 0) return
          const target = event.target as Element
          if (target.closest('[role="button"]')) return
          userAdjustedView.current = true
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
                width={plotWidth + treeSpacing * 0.9}
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
              const { x, y } = schematicXY(tree, rowSpacing, treeSpacing)
              return (
                <TreeDot
                  key={tree.id}
                  tree={tree}
                  x={x}
                  y={y}
                  radius={radius}
                  color={tree.variety ? colors.get(tree.variety) : undefined}
                  selected={tree.id === selectedTreeId || selectedTreeIds.includes(tree.id)}
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
        <MapButton label={tr('Početni prikaz')} onClick={resetView} />
      </div>

      {showLegend ? (
        <div
          className={cn(
            'pointer-events-none absolute inset-x-0 bottom-0 z-10 p-3',
            selectedTreeId && 'max-lg:pb-16',
          )}
        >
          <div className="pointer-events-auto inline-flex max-w-full flex-wrap gap-2 rounded-xl border border-border/70 bg-card/95 px-3 py-2 text-xs shadow-md">
            {varieties.map((item) => (
              <span key={item.name} className="inline-flex items-center gap-1.5 text-muted-foreground">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: item.color }} />
                <span>{item.name}</span>
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
              <span className="h-2.5 w-2.5 rounded-full border border-dashed border-muted-foreground bg-transparent" />
              {tr('Izostanak sadnice')}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function TreeDot({
  tree,
  x,
  y,
  radius,
  color,
  selected,
  dimmed,
  faint,
  onSelect,
}: {
  tree: TreeMapItem
  x: number
  y: number
  radius: number
  color?: string
  selected: boolean
  dimmed: boolean
  faint: boolean
  onSelect: () => void
}) {
  const missing = tree.status === 'removed'
  const healthClass = treeMarkerClass(tree.status, tree.health_status, Boolean(tree.has_severe_case))
  const useVarietyColor = Boolean(color) && tree.status === 'active'
  const hitRadius = radius * 2.6
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
      onPointerDown={(event) => {
        // Keep map pan from stealing the first tap on a tree.
        event.stopPropagation()
      }}
    >
      {/* Larger invisible hit target for touch. */}
      <circle cx={x} cy={y} r={hitRadius} className="fill-transparent" />
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
