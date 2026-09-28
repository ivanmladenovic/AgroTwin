import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Filter } from 'lucide-react'

import { getOrchardTwin, getTreeDetail } from '@/features/orchard/api'
import { orchardFilters, type OrchardTreeFilter } from '@/features/orchard/health'
import { OrchardCanvas } from '@/features/orchard/OrchardCanvas'
import { ParcelSummary } from '@/features/orchard/ParcelSummary'
import { ParcelWeatherForecast } from '@/features/orchard/ParcelWeatherForecast'
import { ParcelSoilCard } from '@/features/orchard/ParcelSoilCard'
import { TreeDrawer } from '@/features/orchard/TreeDrawer'
import { TreeNavPad } from '@/features/orchard/TreeNavPad'
import { canNavigate, neighborTreeId, type TreeNavDirection } from '@/features/orchard/treeNavigation'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

export function OrchardMapPage() {
  const { parcelId } = useParams()
  const [searchParams] = useSearchParams()
  const [selectedTreeId, setSelectedTreeId] = useState<string | null>(null)
  const [healthFilter, setHealthFilter] = useState<OrchardTreeFilter>(() => parseHealthFilter(searchParams.get('health')))

  const twinQuery = useQuery({
    queryKey: ['orchard-twin', parcelId],
    queryFn: () => getOrchardTwin(parcelId!),
    enabled: Boolean(parcelId),
  })
  const treeQuery = useQuery({
    queryKey: ['tree-detail', parcelId, selectedTreeId],
    queryFn: () => getTreeDetail(parcelId!, selectedTreeId!),
    enabled: Boolean(parcelId && selectedTreeId),
  })

  const twin = twinQuery.data
  const selectedRowIds = useMemo(() => {
    const rowNumber = Number(searchParams.get('row') || '')
    if (!twin || !Number.isInteger(rowNumber) || rowNumber <= 0) return []
    return twin.rows.filter((row) => row.row_number === rowNumber).map((row) => row.id)
  }, [searchParams, twin])
  const visibleCount = useMemo(() => {
    if (!twin) return 0
    const plantedTrees = twin.trees.filter((tree) => tree.status !== 'removed')
    if (healthFilter === 'missing') {
      const perRow = twin.stats.trees_per_row ?? twin.parcel.trees_per_row ?? 0
      return Math.max(twin.stats.row_count * perRow - plantedTrees.length, 0)
    }
    if (healthFilter === 'attention') {
      return plantedTrees.filter((tree) => tree.health_status === 'issue' || tree.health_status === 'monitoring').length
    }
    if (healthFilter === 'all') return plantedTrees.length
    return plantedTrees.filter((tree) => tree.health_status === healthFilter).length
  }, [healthFilter, twin])

  const navEnabled = useMemo(() => {
    if (!twin || !selectedTreeId) {
      return { up: false, down: false, left: false, right: false }
    }
    return canNavigate(twin.trees, selectedTreeId)
  }, [selectedTreeId, twin])

  function handleNavigate(direction: TreeNavDirection) {
    if (!twin || !selectedTreeId) return
    const nextId = neighborTreeId(twin.trees, selectedTreeId, direction)
    if (nextId) setSelectedTreeId(nextId)
  }

  if (!parcelId) return null
  if (twinQuery.isLoading) {
    return <div className="w-full text-sm text-muted-foreground">Učitavanje zasada…</div>
  }
  if (!twin) {
    return <div className="w-full text-sm text-danger">Parcela nije pronađena.</div>
  }

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold sm:text-2xl">{twin.parcel.name}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {twin.stats.row_count} redova · {formatNumber(twin.stats.total_trees)} stabala
            {healthFilter === 'all' ? null : ` · ${formatNumber(visibleCount)} prikazano`}
          </p>
          {twin.parcel.maps_url ? (
            <a
              href={twin.parcel.maps_url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex text-sm font-medium text-primary hover:underline"
            >
              Otvori na Google Maps
            </a>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/orchard/${parcelId}/production`}>
            <Button variant="outline" size="sm">
              Proizvodnja
            </Button>
          </Link>
          <Link to={`/orchard/${parcelId}/report`}>
            <Button variant="outline" size="sm">
              Godišnji izveštaj
            </Button>
          </Link>
        </div>
      </div>

      <ParcelSummary stats={twin.stats} />

      <ParcelWeatherForecast parcelId={parcelId} />
      <ParcelSoilCard parcelId={parcelId} />

      <div className="relative z-30 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <FilterMenu value={healthFilter} onChange={setHealthFilter} />
        <div className="flex flex-wrap items-center gap-2">
          <Link to={`/orchard/${parcelId}/edit`}>
            <Button variant="outline" size="sm">
              Izmeni parcelu
            </Button>
          </Link>
          <Link to={`/activities/new?scope=parcel&parcelId=${parcelId}&returnTo=/orchard/${parcelId}`}>
            <Button size="sm">+ Dodaj aktivnost</Button>
          </Link>
        </div>
      </div>

      <div className="relative min-h-[min(58dvh,32rem)] overflow-hidden rounded-2xl border border-border lg:min-h-[min(70vh,40rem)]">
        <OrchardCanvas
          twin={twin}
          selectedTreeId={selectedTreeId}
          healthFilter={healthFilter}
          selectedRowIds={selectedRowIds}
          onSelectTree={setSelectedTreeId}
          focusTreeId={selectedTreeId}
        />

        {selectedTreeId ? (
          <div className="absolute bottom-14 left-2 z-30 lg:hidden">
            <TreeNavPad enabled={navEnabled} onNavigate={handleNavigate} />
          </div>
        ) : null}

        {selectedTreeId && treeQuery.data ? (
          <div className="absolute inset-y-2 right-2 z-20 w-[min(12.5rem,46%)] overflow-hidden rounded-xl border border-border shadow-lg lg:inset-y-0 lg:right-0 lg:left-auto lg:w-96 lg:rounded-none lg:border-y-0 lg:border-r-0">
            <TreeDrawer
              tree={treeQuery.data}
              parcelId={parcelId}
              onClose={() => setSelectedTreeId(null)}
            />
          </div>
        ) : null}
      </div>
    </div>
  )
}

function FilterMenu({
  value,
  onChange,
}: {
  value: OrchardTreeFilter
  onChange: (value: OrchardTreeFilter) => void
}) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={menuRef} className="relative">
      <Button
        type="button"
        variant="outline"
        onClick={() => setOpen((current) => !current)}
        className={value !== 'all' ? 'border-primary text-primary' : undefined}
      >
        <Filter className="h-4 w-4" />
        Filter
        <ChevronDown className="h-4 w-4" />
      </Button>
      {open ? (
        <div className="absolute left-0 z-30 mt-2 w-56 rounded-xl border border-border bg-card p-1 shadow-md">
          {orchardFilters.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => {
                onChange(item.value)
                setOpen(false)
              }}
              className={cn(
                'flex min-h-11 w-full items-center rounded-lg px-3 py-2.5 text-left text-sm',
                item.value === value ? 'bg-primary/10 font-medium text-primary' : 'hover:bg-muted',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function parseHealthFilter(value: string | null): OrchardTreeFilter {
  if (
    value === 'healthy' ||
    value === 'monitoring' ||
    value === 'issue' ||
    value === 'unknown' ||
    value === 'missing' ||
    value === 'attention'
  ) {
    return value
  }
  return 'all'
}
