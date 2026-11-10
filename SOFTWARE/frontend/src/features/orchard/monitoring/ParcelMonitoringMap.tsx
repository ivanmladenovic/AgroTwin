import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import {
  GeoJSON,
  ImageOverlay,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  TileLayer,
  ZoomControl,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { clipPolygonByPolygon, ringLngLatFromGeometry } from '@/features/orchard/monitoring/clipPolygon'
import { STRETCH, indexLegendGradient, indexToColor } from '@/features/orchard/monitoring/ndviScale'
import { zoneKeyLabel } from '@/features/orchard/monitoring/satelliteLabels'
import type { SatelliteSample, SatelliteZone, VisualizationLayer } from '@/shared/api/types'
import { fetchObjectUrl } from '@/shared/lib/api'
import { parcelCoordinates } from '@/shared/lib/maps'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'
export type BasemapId = 'osm' | 'esri'
export type IndexLayerId = 'ndvi' | 'ndre' | 'ndwi'

/** Fixed satellite index overlay opacity (90%). */
const SATELLITE_OVERLAY_OPACITY = 0.9

type ParcelLike = {
  name: string
  area_hectares: string | null
  latitude: string | null
  longitude: string | null
  boundary: Record<string, unknown> | null
}

export type MapInspectPoint = {
  lat: number
  lng: number
  sample: SatelliteSample | null
  loading: boolean
}

type Props = {
  parcel: ParcelLike
  zones: SatelliteZone[]
  indexLayer: VisualizationLayer | null
  activeIndex: IndexLayerId | null
  availableIndices: IndexLayerId[]
  showZones?: boolean
  onActiveIndexChange: (id: IndexLayerId | null) => void
  selectedZoneKey: string | null
  onSelectZone: (zoneKey: string | null) => void
  onMapInspect?: (lat: number, lng: number) => void
  inspectPoint?: MapInspectPoint | null
  onClearInspect?: () => void
  dateLabel?: string | null
  compactControls?: boolean
  /**
   * Profile embed: fill parent, show only NDVI/NDRE/NDWI chips + compact legend.
   */
  embedded?: boolean
  className?: string
  allowDrawBoundary?: boolean
  onBoundarySave?: (boundary: GeoJSON.Polygon) => void | Promise<void>
  boundarySaving?: boolean
}

/** Free Esri World Imagery — fixed basemap (not the dated Sentinel-2 observation). */
const ESRI = {
  url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
}

const BOUNDARY_STYLE: L.PathOptions = {
  color: '#facc15',
  weight: 3.5,
  opacity: 1,
  fillColor: '#facc15',
  fillOpacity: 0.04,
}

const DRAFT_STYLE: L.PathOptions = {
  color: '#f59e0b',
  weight: 2.5,
  opacity: 1,
  dashArray: '6 4',
  fillColor: '#f59e0b',
  fillOpacity: 0.12,
}

const INDEX_LABELS: Record<IndexLayerId, string> = {
  ndvi: 'NDVI',
  ndre: 'NDRE',
  ndwi: 'NDWI',
}

/** Plain-language legend copy — call at render time so locale switches apply. */
function indexPlainHelp(id: IndexLayerId): string {
  switch (id) {
    case 'ndvi':
      return tr(
        'Gledajte žute, narandžaste i crvene delove — tu sadnice izgledaju slabije ili sitnije. Zelenije = bujnije i jače. Fokus na slabije delove, ne na zelene.',
      )
    case 'ndre':
      return tr(
        'Isto kao NDVI, malo osetljivije. Narandžasto/crveno = slabiji deo zasada; zeleno = jači. Prvo obiđite slabije delove.',
      )
    case 'ndwi':
      return tr(
        'Narandžasto/crvenije može značiti da biljke deluju suvlje. Nije mera zalivanja — samo signal gde da proverite prvo.',
      )
  }
}

function FitToParcel({
  boundary,
  center,
  locked,
}: {
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  center: [number, number] | null
  locked?: boolean
}) {
  const map = useMap()
  useEffect(() => {
    if (locked) return
    if (boundary) {
      const layer = L.geoJSON(boundary as GeoJSON.GeoJsonObject)
      const bounds = layer.getBounds()
      if (bounds.isValid()) {
        // Default framing ≈ fit + one Leaflet "+" click (tighter on the parcel).
        map.fitBounds(bounds.pad(0.18), { animate: false })
        map.setZoom(map.getZoom() + 1, { animate: false })
        return
      }
    }
    if (center) map.setView(center, 16, { animate: false })
  }, [boundary, center, locked, map])
  return null
}

function MapResizeHandler({ containerRef }: { containerRef: RefObject<HTMLDivElement | null> }) {
  const map = useMap()
  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined
    const refresh = () => map.invalidateSize()
    const t = window.setTimeout(refresh, 50)
    const observer = new ResizeObserver(refresh)
    observer.observe(el)
    return () => {
      window.clearTimeout(t)
      observer.disconnect()
    }
  }, [containerRef, map])
  return null
}

function DrawClickHandler({
  enabled,
  onAddPoint,
}: {
  enabled: boolean
  onAddPoint: (point: [number, number]) => void
}) {
  const map = useMap()
  useEffect(() => {
    if (!enabled) {
      map.getContainer().style.cursor = ''
      return undefined
    }
    map.getContainer().style.cursor = 'crosshair'
    return () => {
      map.getContainer().style.cursor = ''
    }
  }, [enabled, map])

  useMapEvents({
    click(event) {
      if (!enabled) return
      onAddPoint([event.latlng.lat, event.latlng.lng])
    },
  })
  return null
}

function InspectClickHandler({
  enabled,
  onInspect,
}: {
  enabled: boolean
  onInspect?: (lat: number, lng: number) => void
}) {
  useMapEvents({
    click(event) {
      if (!enabled || !onInspect) return
      onInspect(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

function clipPathForOverlay(
  imageBounds: L.LatLngBounds,
  clipRing: [number, number][] | null,
): string {
  if (!clipRing || clipRing.length < 3) return ''
  const west = imageBounds.getWest()
  const east = imageBounds.getEast()
  const south = imageBounds.getSouth()
  const north = imageBounds.getNorth()
  const width = east - west
  const height = north - south
  if (width <= 0 || height <= 0) return ''
  const points = clipRing.map(([lat, lng]) => {
    const x = ((lng - west) / width) * 100
    const y = ((north - lat) / height) * 100
    return `${x.toFixed(3)}% ${y.toFixed(3)}%`
  })
  return `polygon(${points.join(', ')})`
}

function AuthImageOverlay({
  layer,
  clipGeometry,
  opacity,
}: {
  layer: VisualizationLayer
  clipGeometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  opacity: number
}) {
  const [url, setUrl] = useState<string | null>(null)
  const overlayRef = useRef<L.ImageOverlay | null>(null)

  const layerRevision = `${layer.url}|${layer.bbox.join(',')}|${layer.width ?? ''}|${layer.height ?? ''}`
  const clipRing = useMemo(
    () => (clipGeometry ? ringLatLngs(clipGeometry as unknown as Record<string, unknown>) : null),
    [clipGeometry],
  )

  useEffect(() => {
    let active = true
    let objectUrl: string | null = null
    setUrl(null)
    void fetchObjectUrl(layer.url)
      .then((next) => {
        if (!active) {
          URL.revokeObjectURL(next)
          return
        }
        objectUrl = next
        setUrl(next)
      })
      .catch(() => {
        if (active) setUrl(null)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [layer.url, layerRevision])

  const bounds = useMemo(() => {
    const [west, south, east, north] = layer.bbox
    if (![west, south, east, north].every((v) => Number.isFinite(v))) return null
    return L.latLngBounds([
      [south, west],
      [north, east],
    ])
  }, [layer.bbox])

  const applyClip = () => {
    const img = overlayRef.current?.getElement()
    if (!img || !bounds) return
    const path = clipPathForOverlay(bounds, clipRing)
    img.style.setProperty('clip-path', path)
    img.style.setProperty('-webkit-clip-path', path)
    img.style.setProperty('image-rendering', 'auto')
    img.classList.add('agrotwin-index-overlay')
  }

  useMapEvents({
    move: applyClip,
    zoom: applyClip,
    moveend: applyClip,
    zoomend: applyClip,
  })

  useEffect(() => {
    applyClip()
  }, [url, bounds, clipRing])

  useEffect(() => {
    overlayRef.current?.setOpacity(opacity)
  }, [opacity])

  if (!url || !bounds) return null
  return (
    <ImageOverlay
      url={url}
      bounds={bounds}
      opacity={opacity}
      zIndex={350}
      className="agrotwin-index-overlay"
      eventHandlers={{
        add: (event) => {
          overlayRef.current = event.target
          applyClip()
        },
        load: () => applyClip(),
      }}
    />
  )
}

function asPolygon(geometry: Record<string, unknown> | null): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (!geometry || typeof geometry.type !== 'string') return null
  if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon') {
    return geometry as unknown as GeoJSON.Polygon | GeoJSON.MultiPolygon
  }
  return null
}

function ringLatLngs(geometry: Record<string, unknown>): [number, number][] | null {
  const type = geometry.type
  const coordinates = geometry.coordinates as unknown
  let ring: number[][] | null = null
  if (type === 'Polygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    ring = coordinates[0] as number[][]
  } else if (type === 'MultiPolygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    const first = coordinates[0] as unknown[]
    if (Array.isArray(first) && Array.isArray(first[0])) ring = first[0] as number[][]
  }
  if (!ring) return null
  return ring.map(([lon, lat]) => [lat, lon] as [number, number])
}

/** Zone grid cells are bbox rectangles — clip to parcel so marks stay on the orchard. */
function clippedZoneLatLngs(
  zoneGeometry: Record<string, unknown>,
  parcelBoundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null,
): [number, number][] | null {
  const zoneRing = ringLngLatFromGeometry(zoneGeometry)
  if (!zoneRing) return null
  if (!parcelBoundary) {
    return zoneRing.map(([lng, lat]) => [lat, lng] as [number, number])
  }
  const parcelRing = ringLngLatFromGeometry(parcelBoundary as unknown as Record<string, unknown>)
  if (!parcelRing) {
    return zoneRing.map(([lng, lat]) => [lat, lng] as [number, number])
  }
  const clipped = clipPolygonByPolygon(zoneRing, parcelRing)
  if (clipped.length < 3) return null
  return clipped.map(([lng, lat]) => [lat, lng] as [number, number])
}

function latLngsToGeoJsonPolygon(points: [number, number][]): GeoJSON.Polygon {
  const ring = points.map(([lat, lon]) => [lon, lat] as [number, number])
  const first = ring[0]
  const last = ring[ring.length - 1]
  if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
    ring.push([first[0], first[1]])
  }
  return { type: 'Polygon', coordinates: [ring] }
}

function boundaryFingerprint(geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon): string {
  try {
    return JSON.stringify(geometry.coordinates)
  } catch {
    return String(Date.now())
  }
}

function MapChip({
  active,
  disabled,
  onClick,
  children,
  title,
}: {
  active?: boolean
  disabled?: boolean
  onClick?: () => void
  children: ReactNode
  title?: string
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex h-8 items-center justify-center rounded-md px-2.5 text-xs font-semibold transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-40',
        active
          ? 'bg-primary text-primary-foreground shadow-sm'
          : 'border border-border/80 bg-white text-foreground hover:bg-muted/80',
      )}
    >
      {children}
    </button>
  )
}

function fmtSample(value: string | null | undefined) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (Number.isNaN(n)) return '—'
  return n.toLocaleString('sr-RS', { maximumFractionDigits: 3 })
}

function InspectSampleDetails({ sample }: { sample: SatelliteSample }) {
  const zone = zoneKeyLabel(sample.zone_key)
  return (
    <>
      <p className="mt-1 text-foreground">
        {INDEX_LABELS[(sample.index as IndexLayerId) || 'ndvi']}:{' '}
        <span className="font-mono font-semibold">{fmtSample(sample.value)}</span>
      </p>
      <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{sample.message}</p>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {tr('Datum')}: {sample.acquisition_date}
        {zone ? ` · ${tr('zona')} ${zone}` : ''}
      </p>
    </>
  )
}

export function ParcelMonitoringMap({
  parcel,
  zones,
  indexLayer,
  activeIndex,
  availableIndices,
  showZones = false,
  onActiveIndexChange,
  selectedZoneKey,
  onSelectZone,
  onMapInspect,
  inspectPoint,
  onClearInspect,
  dateLabel,
  compactControls = false,
  embedded = false,
  className,
  allowDrawBoundary = false,
  onBoundarySave,
  boundarySaving = false,
}: Props) {
  useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const [mounted, setMounted] = useState(false)
  const [drawing, setDrawing] = useState(false)
  const [draftPoints, setDraftPoints] = useState<[number, number][]>([])
  const [layerPanelOpen, setLayerPanelOpen] = useState(Boolean(activeIndex))
  const [lastIndex, setLastIndex] = useState<IndexLayerId>(activeIndex ?? 'ndvi')
  const boundary = useMemo(() => asPolygon(parcel.boundary), [parcel.boundary])
  const coords = parcelCoordinates(parcel)
  const center: [number, number] | null = coords ? [coords.lat, coords.lng] : null
  const indexAvailable = Boolean(indexLayer && activeIndex)
  const canFinishDraw = draftPoints.length >= 3
  const stretch = STRETCH[activeIndex ?? 'ndvi']
  const layerVisible = Boolean(activeIndex)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (activeIndex) {
      setLastIndex(activeIndex)
      setLayerPanelOpen(true)
    }
  }, [activeIndex])

  function toggleLayerPanel() {
    if (layerVisible) {
      onActiveIndexChange(null)
      setLayerPanelOpen(false)
      onClearInspect?.()
      return
    }
    const preferred =
      availableIndices.includes(lastIndex)
        ? lastIndex
        : availableIndices.includes('ndvi')
          ? 'ndvi'
          : availableIndices[0] ?? null
    onActiveIndexChange(preferred)
    setLayerPanelOpen(true)
  }

  function startDrawing() {
    setDrawing(true)
    setDraftPoints([])
    onClearInspect?.()
  }

  function cancelDrawing() {
    setDrawing(false)
    setDraftPoints([])
  }

  async function finishDrawing() {
    if (!canFinishDraw || !onBoundarySave || boundarySaving) return
    const polygon = latLngsToGeoJsonPolygon(draftPoints)
    try {
      await onBoundarySave(polygon)
      setDrawing(false)
      setDraftPoints([])
    } catch {
      // Parent shows the error; keep draft so the user can retry or adjust points.
    }
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        'agrotwin-map-root relative overflow-hidden bg-muted/40',
        embedded
          ? 'h-full min-h-0 rounded-none border-0'
          : 'h-[min(78vh,720px)] min-h-[360px] rounded-2xl border border-border',
        className,
      )}
    >
      {mounted ? (
        <MapContainer
          center={center ?? [44.05, 20.55]}
          zoom={center ? 15 : 7}
          minZoom={5}
          maxZoom={19}
          scrollWheelZoom
          attributionControl={false}
          zoomControl={false}
          className="h-full w-full"
          style={{ height: '100%', width: '100%' }}
          doubleClickZoom={!drawing}
        >
          <TileLayer url={ESRI.url} maxZoom={19} />
          <ZoomControl position="bottomright" />
          <MapResizeHandler containerRef={containerRef} />
          <FitToParcel boundary={boundary} center={center} locked={drawing} />
          <DrawClickHandler
            enabled={drawing}
            onAddPoint={(point) => setDraftPoints((prev) => [...prev, point])}
          />
          <InspectClickHandler enabled={!drawing && Boolean(onMapInspect)} onInspect={onMapInspect} />

          {indexAvailable && indexLayer ? (
            <AuthImageOverlay
              layer={indexLayer}
              clipGeometry={boundary}
              opacity={SATELLITE_OVERLAY_OPACITY}
            />
          ) : null}

          {boundary && !drawing ? (
            <GeoJSON
              key={`boundary-${boundaryFingerprint(boundary)}`}
              data={boundary as GeoJSON.GeoJsonObject}
              style={BOUNDARY_STYLE}
            />
          ) : null}

          {drawing && draftPoints.length >= 2 ? (
            draftPoints.length >= 3 ? (
              <Polygon positions={draftPoints} pathOptions={DRAFT_STYLE} />
            ) : (
              <Polyline positions={draftPoints} pathOptions={DRAFT_STYLE} />
            )
          ) : null}

          {drawing
            ? draftPoints.map((point, idx) => (
                <Marker
                  key={`draft-${idx}`}
                  position={point}
                  icon={L.divIcon({
                    className: 'agrotwin-map-marker',
                    html: `<span style="display:block;width:10px;height:10px;border-radius:9999px;background:#f59e0b;border:2px solid #fff;box-shadow:0 1px 4px rgba(16,36,26,0.35)"></span>`,
                    iconSize: [10, 10],
                    iconAnchor: [5, 5],
                  })}
                />
              ))
            : null}

          {!boundary && !drawing && center ? (
            <Marker
              position={center}
              icon={L.divIcon({
                className: 'agrotwin-map-marker',
                html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:#facc15;border:2px solid #fff;box-shadow:0 1px 6px rgba(16,36,26,0.35)"></span>`,
                iconSize: [14, 14],
                iconAnchor: [7, 7],
              })}
            />
          ) : null}

          {inspectPoint ? (
            <Marker
              position={[inspectPoint.lat, inspectPoint.lng]}
              icon={L.divIcon({
                className: 'agrotwin-map-marker',
                html: `<span style="display:block;width:12px;height:12px;border-radius:9999px;background:#0f766e;border:2px solid #fff;box-shadow:0 1px 6px rgba(16,36,26,0.4)"></span>`,
                iconSize: [12, 12],
                iconAnchor: [6, 6],
              })}
            />
          ) : null}

          {showZones && !drawing
            ? zones.map((zone) => {
                const latlngs = clippedZoneLatLngs(zone.geometry, boundary)
                if (!latlngs) return null
                const zoneIndex = activeIndex ?? 'ndvi'
                const raw =
                  zoneIndex === 'ndre'
                    ? zone.ndre
                    : zoneIndex === 'ndwi'
                      ? zone.ndwi
                      : zone.ndvi
                const value = raw != null ? Number(raw) : null
                const selected = selectedZoneKey === zone.zone_key
                return (
                  <Polygon
                    key={zone.zone_key}
                    positions={latlngs}
                    pathOptions={{
                      color: selected ? '#0f172a' : '#ffffff',
                      weight: selected ? 2.5 : 1,
                      fillColor: indexToColor(value, zoneIndex),
                      fillOpacity: 0.45,
                    }}
                    eventHandlers={{
                      click: () => onSelectZone(zone.zone_key),
                    }}
                  />
                )
              })
            : null}
        </MapContainer>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">{tr('Učitavanje mape…')}</p>
        </div>
      )}

      <div
        className={cn(
          'pointer-events-none absolute inset-x-0 top-0 z-[500] flex items-start justify-between gap-2',
          embedded ? 'p-2' : 'gap-3 p-3',
        )}
      >
        <div className="pointer-events-auto max-w-[min(100%,18rem)] space-y-2">
          {!embedded ? (
            <div className="rounded-xl border border-border/80 bg-white/95 px-3 py-2 shadow-md backdrop-blur-sm">
              <p className="text-sm font-semibold text-foreground">{parcel.name}</p>
              {dateLabel ? (
                <p className="text-xs font-medium text-foreground/80">
                  Sentinel-2 opservacija: {dateLabel}
                </p>
              ) : null}
              {parcel.area_hectares ? (
                <p className="text-xs text-muted-foreground">{Number(parcel.area_hectares).toFixed(2)} ha</p>
              ) : null}
              {drawing ? (
                <p className="mt-1.5 text-[11px] font-medium leading-snug text-amber-800">
                  {tr(
                    'Kliknite na mapu da dodate tačke ({{count}}). Minimum 3 tačke, zatim „Sačuvaj“.',
                    { count: draftPoints.length },
                  )}
                </p>
              ) : null}
            </div>
          ) : dateLabel ? (
            <div className="rounded-lg border border-border/80 bg-white/95 px-2 py-1 text-[11px] font-medium text-foreground shadow-sm backdrop-blur-sm">
              Sentinel-2 · {dateLabel}
            </div>
          ) : null}

          {inspectPoint && !compactControls && !embedded ? (
            <div className="rounded-xl border border-border/80 bg-white/95 px-3 py-2 text-xs shadow-md backdrop-blur-sm">
              <div className="flex items-start justify-between gap-2">
                <p className="font-semibold text-foreground">{tr('Pregled tačke')}</p>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => onClearInspect?.()}
                >
                  {tr('Zatvori')}
                </button>
              </div>
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                {inspectPoint.lat.toFixed(5)}, {inspectPoint.lng.toFixed(5)}
              </p>
              {inspectPoint.loading ? (
                <p className="mt-1 text-muted-foreground">{tr('Učitavanje…')}</p>
              ) : inspectPoint.sample ? (
                <InspectSampleDetails sample={inspectPoint.sample} />
              ) : null}
            </div>
          ) : null}
        </div>

        {embedded ? (
          <div className="pointer-events-auto flex max-w-[min(100%,14rem)] flex-col gap-1.5 rounded-lg border border-border/80 bg-white/95 p-1.5 shadow-md backdrop-blur-sm">
            <div className="flex flex-wrap gap-1">
              {(['ndvi', 'ndre', 'ndwi'] as const).map((id) => {
                const available = availableIndices.includes(id)
                const isActive = activeIndex === id
                return (
                  <MapChip
                    key={id}
                    active={isActive}
                    disabled={!available}
                    title={indexPlainHelp(id)}
                    onClick={() => onActiveIndexChange(id)}
                  >
                    {INDEX_LABELS[id]}
                  </MapChip>
                )
              })}
            </div>
          </div>
        ) : !compactControls ? (
          <div className="pointer-events-auto flex max-w-[min(100%,22rem)] flex-col gap-2 rounded-xl border border-border/80 bg-white/95 p-2 shadow-md backdrop-blur-sm">
            <div className="flex flex-wrap gap-1.5">
              <MapChip
                active={layerVisible}
                disabled={availableIndices.length === 0 || drawing}
                onClick={toggleLayerPanel}
                title={
                  layerVisible
                    ? tr('Ukloni satelitski sloj sa mape')
                    : tr('Prikaži satelitski sloj na parceli')
                }
              >
                {layerVisible ? tr('Ukloni sloj') : tr('Prikaz sloja')}
              </MapChip>
              {allowDrawBoundary && onBoundarySave && !drawing ? (
                <MapChip onClick={startDrawing} title={tr('Nacrtajte ili zamenite granicu parcele na mapi')}>
                  {boundary ? tr('Izmeni granicu') : tr('Nacrtaj granicu')}
                </MapChip>
              ) : null}
            </div>

            {drawing && allowDrawBoundary && onBoundarySave ? (
              <div className="flex flex-wrap gap-1.5 border-t border-border/60 pt-2">
                <MapChip
                  active
                  disabled={!canFinishDraw || boundarySaving}
                  onClick={() => void finishDrawing()}
                >
                  {boundarySaving ? tr('Čuvanje…') : tr('Sačuvaj')}
                </MapChip>
                <MapChip
                  disabled={draftPoints.length === 0 || boundarySaving}
                  onClick={() => setDraftPoints((prev) => prev.slice(0, -1))}
                >
                  {tr("Nazad")}
                </MapChip>
                <MapChip disabled={boundarySaving} onClick={cancelDrawing}>
                  {tr('Otkaži')}
                </MapChip>
              </div>
            ) : null}

            {layerPanelOpen && layerVisible ? (
              <div className="border-t border-border/60 pt-2">
                <p className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {tr('Indeks')}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {(['ndvi', 'ndre', 'ndwi'] as const).map((id) => {
                    const available = availableIndices.includes(id)
                    const isActive = activeIndex === id
                    return (
                      <MapChip
                        key={id}
                        active={isActive}
                        disabled={!available}
                        title={indexPlainHelp(id)}
                        onClick={() => onActiveIndexChange(id)}
                      >
                        {INDEX_LABELS[id]}
                      </MapChip>
                    )
                  })}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {indexAvailable && activeIndex && !drawing ? (
        <div
          className={cn(
            'pointer-events-none absolute z-[500]',
            embedded
              ? 'bottom-2 left-2 max-w-[min(100%,18rem)]'
              : 'bottom-3 left-3 max-w-[min(100%,22rem)]',
          )}
        >
          <div
            className={cn(
              'pointer-events-auto border border-border/80 bg-white/95 shadow-md backdrop-blur-sm',
              embedded ? 'rounded-lg px-2.5 py-2 text-[10px]' : 'rounded-xl px-3 py-2 text-xs',
            )}
          >
            <p className="font-medium text-foreground">{INDEX_LABELS[activeIndex]}</p>
            <div
              className={cn('w-full rounded-sm border border-black/10', embedded ? 'mt-1 h-2' : 'mt-2 h-2.5')}
              style={{ background: indexLegendGradient(activeIndex) }}
            />
            <div className="mt-0.5 flex justify-between text-[9px] text-muted-foreground">
              <span>{tr('slabije (kritično)')}</span>
              <span>{tr('bujnije')}</span>
            </div>
            <p
              className={cn(
                'leading-snug text-muted-foreground',
                embedded ? 'mt-1.5 text-[10px]' : 'mt-1.5 text-[11px]',
              )}
            >
              {indexPlainHelp(activeIndex)}
            </p>
            {!embedded ? (
              <p className="mt-1 font-mono text-[10px] text-muted-foreground/80">
                {tr('skala {{min}} … {{max}}', {
                  min: stretch.vmin.toFixed(1),
                  max: stretch.vmax.toFixed(1),
                })}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      {!boundary && !center && !drawing ? (
        <div className="pointer-events-none absolute inset-0 z-[400] flex items-center justify-center p-6">
          <p className="rounded-xl border border-border bg-white/95 px-4 py-3 text-center text-sm text-muted-foreground">
            {tr('Nema lokacije parcele. Unesite Google Maps link ili nacrtajte granicu na mapi.')}
          </p>
        </div>
      ) : null}
    </div>
  )
}
