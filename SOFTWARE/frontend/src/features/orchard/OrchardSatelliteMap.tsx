import { useEffect, useMemo } from 'react'
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polygon,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { ringLatLngFromBoundary, rowLabelLatLng } from '@/features/orchard/geoLocal'
import type { OrchardTreeFilter } from '@/features/orchard/health'
import { varietyColorMap, varietiesFromTwin } from '@/features/orchard/varieties'
import type { OrchardTwin, TreeMapItem } from '@/shared/api/types'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'
/** Google satellite — reliable high-zoom coverage in Serbia. */
const SATELLITE_URL = 'https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
const SATELLITE_SUBDOMAINS = '0123'

type Props = {
  twin: OrchardTwin
  selectedTreeId: string | null
  healthFilter?: OrchardTreeFilter
  onSelectTree?: (treeId: string) => void
  className?: string
}

function FitParcel({
  ring,
  trees,
  labels = [],
}: {
  ring: [number, number][]
  trees: Array<{ lat: number; lng: number }>
  labels?: Array<{ lat: number; lng: number }>
}) {
  const map = useMap()
  useEffect(() => {
    const bounds = L.latLngBounds([])
    const source =
      trees.length > 0 ? trees.map((t) => [t.lat, t.lng] as [number, number]) : ring
    for (const p of source) bounds.extend(p)
    for (const p of labels) bounds.extend([p.lat, p.lng])
    if (!bounds.isValid()) return

    const fit = () => {
      map.invalidateSize()
      map.fitBounds(bounds.pad(0.02), { animate: false, maxZoom: 20 })
      const nextZoom = Math.min(20, map.getZoom() + 0.75)
      map.setZoom(nextZoom, { animate: false })
    }

    requestAnimationFrame(fit)
    const timeout = window.setTimeout(fit, 120)
    const container = map.getContainer()
    const observer =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => {
            map.invalidateSize()
          })
        : null
    if (observer) observer.observe(container)

    return () => {
      window.clearTimeout(timeout)
      observer?.disconnect()
    }
  }, [map, ring, trees, labels])
  return null
}

function treeVisible(tree: TreeMapItem, healthFilter: OrchardTreeFilter) {
  const missing = tree.status === 'removed'
  if (healthFilter === 'all') return { dimmed: false, faint: missing }
  if (healthFilter === 'missing') return { dimmed: !missing, faint: false }
  if (healthFilter === 'attention') {
    const needsAttention = tree.health_status === 'issue' || tree.health_status === 'monitoring'
    return { dimmed: missing || !needsAttention, faint: false }
  }
  return { dimmed: missing || tree.health_status !== healthFilter, faint: false }
}

function rowNumberIcon(rowNumber: number) {
  const label = String(rowNumber).padStart(2, '0')
  return L.divIcon({
    className: 'orchard-row-number-icon',
    html: `<div style="
      color:#f8fafc;font:700 9px/1 Montserrat,system-ui,sans-serif;
      text-shadow:0 0 2px rgba(0,0,0,1),0 1px 2px rgba(0,0,0,0.9);
      white-space:nowrap;pointer-events:none;letter-spacing:0.02em;
    ">${label}</div>`,
    iconSize: [16, 10],
    iconAnchor: [8, 5],
  })
}

export function OrchardSatelliteMap({
  twin,
  selectedTreeId,
  healthFilter = 'all',
  onSelectTree,
  className,
}: Props) {
  const ring = useMemo(() => ringLatLngFromBoundary(twin.parcel.boundary), [twin.parcel.boundary])
  const colors = varietyColorMap(varietiesFromTwin(twin))
  const geoTrees = useMemo(
    () =>
      twin.trees
        .filter((t) => t.latitude != null && t.longitude != null)
        .map((t) => ({
          tree: t,
          lat: Number(t.latitude),
          lng: Number(t.longitude),
        }))
        .filter((t) => Number.isFinite(t.lat) && Number.isFinite(t.lng)),
    [twin.trees],
  )
  const rowMarkers = useMemo(
    () => rowLabelLatLng(geoTrees, ring),
    [geoTrees, ring],
  )

  const center = useMemo((): [number, number] => {
    if (ring.length) {
      const lat = ring.reduce((s, p) => s + p[0], 0) / ring.length
      const lng = ring.reduce((s, p) => s + p[1], 0) / ring.length
      return [lat, lng]
    }
    if (geoTrees.length) return [geoTrees[0]!.lat, geoTrees[0]!.lng]
    if (twin.parcel.latitude != null && twin.parcel.longitude != null) {
      return [Number(twin.parcel.latitude), Number(twin.parcel.longitude)]
    }
    return [44.26, 21.1]
  }, [ring, geoTrees, twin.parcel.latitude, twin.parcel.longitude])

  if (geoTrees.length === 0 && ring.length === 0) {
    return (
      <div
        className={cn(
          'flex h-full w-full items-center justify-center bg-muted px-4 text-center text-sm text-muted-foreground',
          className,
        )}
      >
        {tr('Nema geografskih koordinata za satelitski pregled. Otvorite map editor i sačuvajte granicu.')}
      </div>
    )
  }

  return (
    <div className={cn('agrotwin-map-root relative h-full w-full overflow-hidden', className)}>
      <MapContainer
        center={center}
        zoom={18}
        maxZoom={20}
        minZoom={5}
        className="h-full w-full bg-muted"
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer url={SATELLITE_URL} subdomains={SATELLITE_SUBDOMAINS} maxZoom={20} />
        <ZoomControl position="topright" />
        <FitParcel ring={ring} trees={geoTrees} labels={rowMarkers} />

        {ring.length >= 3 ? (
          <Polygon
            positions={ring}
            pathOptions={{
              color: '#eab308',
              weight: 2.5,
              fillColor: '#eab308',
              fillOpacity: 0.06,
            }}
          />
        ) : null}

        {geoTrees.map(({ tree, lat, lng }) => {
          const visibility = treeVisible(tree, healthFilter)
          const selected = tree.id === selectedTreeId
          const varietyColor = tree.variety ? colors.get(tree.variety) : undefined
          const fill =
            varietyColor && tree.status !== 'removed'
              ? varietyColor
              : tree.status === 'removed'
                ? '#94a3b8'
                : tree.health_status === 'issue' || tree.has_severe_case
                  ? '#dc2626'
                  : tree.health_status === 'monitoring'
                    ? '#ca8a04'
                    : '#0ea5e9'
          return (
            <CircleMarker
              key={tree.id}
              center={[lat, lng]}
              radius={selected ? 5 : 3.25}
              pathOptions={{
                color: selected ? '#ffffff' : fill,
                fillColor: fill,
                fillOpacity: visibility.dimmed ? 0.18 : visibility.faint ? 0.4 : 0.92,
                weight: selected ? 2 : 0.75,
                opacity: visibility.dimmed ? 0.3 : 1,
              }}
              eventHandlers={{
                click: (e) => {
                  L.DomEvent.stopPropagation(e)
                  onSelectTree?.(tree.id)
                },
              }}
            >
              <Tooltip direction="top" opacity={0.95}>
                {tree.public_id}
                {tree.variety ? ` · ${tree.variety}` : ''}
              </Tooltip>
            </CircleMarker>
          )
        })}

        {rowMarkers.map((row) => (
          <Marker
            key={`row-label-${row.rowNumber}`}
            position={[row.lat, row.lng]}
            icon={rowNumberIcon(row.rowNumber)}
            interactive={false}
            zIndexOffset={400}
          />
        ))}
      </MapContainer>
    </div>
  )
}
