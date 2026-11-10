import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Activity,
  ChevronDown,
  FileText,
  Filter,
  LayoutGrid,
  Map as MapIcon,
  MapPinned,
  Pencil,
  Plus,
  Satellite,
  Sprout,
} from 'lucide-react'

import { getOrchardTwin, getTreeDetail, warmParcelEnvironment } from '@/features/orchard/api'
import { getOrchardFilters, type OrchardTreeFilter } from '@/features/orchard/health'
import { OrchardCanvas } from '@/features/orchard/OrchardCanvas'
import { OrchardIndicesMap } from '@/features/orchard/OrchardIndicesMap'
import { OrchardSatelliteMap } from '@/features/orchard/OrchardSatelliteMap'
import { ParcelIntelligenceCard } from '@/features/orchard/ParcelIntelligenceCard'
import { ParcelSatelliteCard } from '@/features/orchard/ParcelSatelliteCard'
import { ParcelSoilCard } from '@/features/orchard/ParcelSoilCard'
import { ParcelSummary } from '@/features/orchard/ParcelSummary'
import { ParcelWeatherForecast } from '@/features/orchard/ParcelWeatherForecast'
import { TreeDetailPanel } from '@/features/orchard/TreeDetailPanel'
import { TreeNavPad } from '@/features/orchard/TreeNavPad'
import { canNavigate, neighborTreeId, type TreeNavDirection } from '@/features/orchard/treeNavigation'
import { varietiesFromTwin } from '@/features/orchard/varieties'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { tr } from '@/shared/i18n/i18n'

type MapViewMode = 'schema' | 'satellite' | 'indices'

export function OrchardMapPage() {
  const { i18n } = useTranslation()
  void i18n.language
  const { parcelId } = useParams()
  const queryClient = useQueryClient()
  const envWarmAttempted = useRef<string | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedTreeId = searchParams.get('tree')
  const [healthFilter, setHealthFilter] = useState<OrchardTreeFilter>(() =>
    parseHealthFilter(searchParams.get('health')),
  )
  const [mapView, setMapView] = useState<MapViewMode>(() => {
    const raw = searchParams.get('map')
    if (raw === 'satellite' || raw === 'indices' || raw === 'schema') return raw
    return 'schema'
  })
  const [mapViewTouched, setMapViewTouched] = useState(false)

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (healthFilter === 'all') next.delete('health')
    else next.set('health', healthFilter)
    if (mapView === 'schema') next.delete('map')
    else next.set('map', mapView)
    if (next.toString() === searchParams.toString()) return
    setSearchParams(next, { replace: true })
  }, [healthFilter, mapView, searchParams, setSearchParams])

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

  useEffect(() => {
    if (!parcelId || !twin) return
    if (envWarmAttempted.current === parcelId) return
    const hasLocation =
      (twin.parcel.latitude != null && twin.parcel.longitude != null) || Boolean(twin.parcel.boundary)
    if (!hasLocation) return
    envWarmAttempted.current = parcelId
    void warmParcelEnvironment(parcelId).then(() => {
      void queryClient.invalidateQueries({ queryKey: ['parcel-weather', parcelId] })
      void queryClient.invalidateQueries({ queryKey: ['parcel-soil', parcelId] })
    })
  }, [parcelId, twin, queryClient])

  useEffect(() => {
    if (!twin || mapViewTouched) return
    const hasGeo =
      Boolean(twin.parcel.boundary) || twin.trees.some((t) => t.latitude != null && t.longitude != null)
    if (hasGeo && mapView === 'schema' && !searchParams.get('map')) {
      setMapView('satellite')
    }
  }, [twin, mapView, mapViewTouched, searchParams])

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
      return plantedTrees.filter((tree) => tree.health_status === 'issue' || tree.health_status === 'monitoring')
        .length
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

  function selectTree(treeId: string | null) {
    const next = new URLSearchParams(searchParams)
    if (treeId) next.set('tree', treeId)
    else next.delete('tree')
    setSearchParams(next, { replace: true })
  }

  function handleNavigate(direction: TreeNavDirection) {
    if (!twin || !selectedTreeId) return
    const nextId = neighborTreeId(twin.trees, selectedTreeId, direction)
    if (nextId) selectTree(nextId)
  }

  useEffect(() => {
    if (!twin || !selectedTreeId) return
    const exists = twin.trees.some((tree) => tree.id === selectedTreeId && tree.status !== 'removed')
    if (exists) return
    const next = new URLSearchParams(searchParams)
    next.delete('tree')
    setSearchParams(next, { replace: true })
  }, [twin, selectedTreeId, searchParams, setSearchParams])

  if (!parcelId) return null
  if (twinQuery.isLoading) {
    return <div className="w-full text-sm text-muted-foreground">{tr('Učitavanje zasada…')}</div>
  }
  if (!twin) {
    return <div className="w-full text-sm text-danger">{tr('Parcela nije pronađena.')}</div>
  }

  const geoLayout = Boolean(
    twin.parcel.map_layout &&
      typeof twin.parcel.map_layout === 'object' &&
      (twin.parcel.map_layout as { source?: string }).source === 'map_editor',
  )
  const hasGeoTrees = twin.trees.some((t) => t.latitude != null && t.longitude != null)
  const canShowSatellite = Boolean(twin.parcel.boundary) || hasGeoTrees
  const varieties = varietiesFromTwin(twin)
  const areaLabel = twin.parcel.area_hectares
    ? `${Number(twin.parcel.area_hectares).toFixed(2)} ha`
    : null
  const activeMapView: MapViewMode =
    mapView === 'satellite' && !canShowSatellite
      ? 'schema'
      : mapView === 'indices' && !canShowSatellite
        ? 'schema'
        : mapView
  const returnTo = encodeURIComponent(
    `/orchard/${parcelId}${searchParams.toString() ? `?${searchParams.toString()}` : ''}`,
  )
  const showTreeChrome = activeMapView === 'schema' || activeMapView === 'satellite'

  function chooseMapView(mode: MapViewMode) {
    setMapViewTouched(true)
    setMapView(mode)
  }

  return (
    <div className="flex w-full flex-col gap-5">
      <header className="min-w-0">
        <p className="kicker">{geoLayout ? tr('Satelitski zasad') : tr('Zasad')}</p>
        <h1 className="mt-1 text-xl font-semibold tracking-tight sm:text-2xl">{twin.parcel.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          <span className="tabular-nums">{twin.stats.row_count}</span> {tr('redova')}
          <span className="mx-1.5 text-border">·</span>
          <span className="tabular-nums">{formatNumber(twin.stats.total_trees)}</span> {tr('stabala')}
          {areaLabel ? (
            <>
              <span className="mx-1.5 text-border">·</span>
              <span className="tabular-nums">{areaLabel}</span>
            </>
          ) : null}
          {twin.parcel.default_planting_year ? (
            <>
              <span className="mx-1.5 text-border">·</span>
              {tr('sadnja {{year}}', { year: twin.parcel.default_planting_year })}
            </>
          ) : null}
          {healthFilter !== 'all' ? (
            <>
              <span className="mx-1.5 text-border">·</span>
              {tr('{{count}} prikazano', { count: formatNumber(visibleCount) })}
            </>
          ) : null}
        </p>
      </header>

      <ParcelSummary
        stats={twin.stats}
        varieties={varieties}
        plantingYear={twin.parcel.default_planting_year}
        compact
      />

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_17.5rem] xl:grid-cols-[minmax(0,1fr)_19rem] lg:items-start">
        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-2.5 py-2">
            <div className="inline-flex flex-wrap rounded-lg border border-border bg-muted/40 p-0.5">
              <MapModeButton
                active={activeMapView === 'schema'}
                onClick={() => chooseMapView('schema')}
                icon={LayoutGrid}
                label={tr('Šema')}
              />
              <MapModeButton
                active={activeMapView === 'satellite'}
                disabled={!canShowSatellite}
                onClick={() => chooseMapView('satellite')}
                icon={MapIcon}
                label={tr('Ortofoto')}
                title={!canShowSatellite ? tr('Nema geografske granice') : tr('Satelitska podloga sa sadnicama')}
              />
              <MapModeButton
                active={activeMapView === 'indices'}
                disabled={!canShowSatellite}
                onClick={() => chooseMapView('indices')}
                icon={Satellite}
                label={tr('Indeksi')}
                title={!canShowSatellite ? tr('Nema geografske granice') : tr('NDVI, NDRE i NDWI')}
              />
            </div>
            {showTreeChrome ? (
              <FilterMenu value={healthFilter} onChange={setHealthFilter} />
            ) : (
              <Link
                to={`/orchard/${parcelId}/satellite`}
                className="text-xs font-medium text-primary hover:underline"
              >
                {tr('Detaljni monitoring')}
              </Link>
            )}
          </div>

          <div className="relative aspect-[16/10] w-full max-h-[min(53vh,31rem)] sm:aspect-[5/3] sm:max-h-[min(50vh,28rem)] lg:max-h-[min(56vh,34rem)]">
            {activeMapView === 'indices' ? (
              <OrchardIndicesMap parcelId={parcelId} twin={twin} />
            ) : activeMapView === 'satellite' ? (
              <OrchardSatelliteMap
                twin={twin}
                selectedTreeId={selectedTreeId}
                healthFilter={healthFilter}
                onSelectTree={selectTree}
              />
            ) : (
              <OrchardCanvas
                twin={twin}
                selectedTreeId={selectedTreeId}
                healthFilter={healthFilter}
                selectedRowIds={selectedRowIds}
                onSelectTree={selectTree}
                focusTreeId={selectedTreeId}
                showLegend={false}
              />
            )}

            {showTreeChrome && selectedTreeId ? (
              <div className="absolute bottom-2 right-2 z-30 lg:hidden">
                <TreeNavPad enabled={navEnabled} onNavigate={handleNavigate} />
              </div>
            ) : null}
          </div>
        </div>

        <aside className="flex flex-col gap-3">
          <div className="rounded-2xl border border-border bg-card p-3 shadow-sm">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {tr('Brze akcije')}
            </p>
            <div className="flex flex-col gap-1.5">
              <QuickAction
                to={`/activities/new?scope=parcel&parcelId=${parcelId}&returnTo=${returnTo}`}
                icon={Plus}
                label={tr('Dodaj aktivnost')}
                primary
              />
              <QuickAction to={`/orchard/${parcelId}/edit`} icon={Pencil} label={tr('Izmeni podatke')} />
              <QuickAction
                to={`/orchard/${parcelId}/map-editor`}
                icon={MapPinned}
                label={geoLayout ? tr('Uredi na mapi') : tr('Map editor')}
              />
              <QuickAction to={`/orchard/${parcelId}/production`} icon={Sprout} label={tr('Proizvodnja')} />
              <QuickAction
                to={`/orchard/${parcelId}/satellite`}
                icon={Satellite}
                label={tr('Detaljni monitoring')}
              />
              <QuickAction to={`/orchard/${parcelId}/report`} icon={FileText} label={tr('Godišnji izveštaj')} />
              <QuickAction
                to={`/health/new?parcelId=${parcelId}&returnTo=${returnTo}`}
                icon={Activity}
                label={tr('Prijavi problem')}
              />
            </div>
          </div>
        </aside>
      </section>

      {selectedTreeId && treeQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje stabla…')}</p>
      ) : null}
      {selectedTreeId && treeQuery.isError ? (
        <p className="text-sm text-danger">{tr('Detalji stabla nisu učitani.')}</p>
      ) : null}
      {selectedTreeId && treeQuery.data ? (
        <TreeDetailPanel
          tree={treeQuery.data}
          parcelId={parcelId}
          onClose={() => selectTree(null)}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <ParcelWeatherForecast parcelId={parcelId} />
        <ParcelSoilCard parcelId={parcelId} />
        <ParcelSatelliteCard parcelId={parcelId} />
        <ParcelIntelligenceCard parcelId={parcelId} />
      </div>
    </div>
  )
}

function QuickAction({
  to,
  icon: Icon,
  label,
  primary = false,
}: {
  to: string
  icon: ComponentType<{ className?: string }>
  label: string
  primary?: boolean
}) {
  return (
    <Link
      to={to}
      className={cn(
        'inline-flex min-h-10 items-center gap-2 rounded-xl px-3 text-sm font-medium transition-colors',
        primary
          ? 'bg-primary text-primary-foreground hover:bg-primary/90'
          : 'border border-border bg-background hover:bg-muted',
      )}
    >
      <Icon className="h-4 w-4 shrink-0 opacity-80" />
      <span className="truncate">{label}</span>
    </Link>
  )
}

function MapModeButton({
  active,
  onClick,
  icon: Icon,
  label,
  disabled,
  title,
}: {
  active: boolean
  onClick: () => void
  icon: ComponentType<{ className?: string }>
  label: string
  disabled?: boolean
  title?: string
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors',
        active ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
        disabled && 'cursor-not-allowed opacity-40',
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
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
  const filters = getOrchardFilters()
  const currentLabel = filters.find((item) => item.value === value)?.label ?? tr('Filter')

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
        size="sm"
        onClick={() => setOpen((current) => !current)}
        className={value !== 'all' ? 'border-primary text-primary' : undefined}
      >
        <Filter className="h-4 w-4" />
        {currentLabel}
        <ChevronDown className="h-4 w-4" />
      </Button>
      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-border bg-card p-1 shadow-md">
          {filters.map((item) => (
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
