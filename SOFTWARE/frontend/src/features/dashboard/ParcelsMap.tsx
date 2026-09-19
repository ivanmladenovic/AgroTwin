import { useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { DashboardParcel } from '@/shared/api/types'
import { formatNumber } from '@/shared/lib/format'
import { parcelCoordinates } from '@/shared/lib/maps'
import { cn } from '@/shared/lib/utils'

const SERBIA_CENTER: [number, number] = [44.05, 20.55]

const MARKER_COLORS = {
  healthy: '#22c55e',
  monitoring: '#c4a017',
  issue: '#ef4444',
} as const

export type ParcelMarkerStatus = keyof typeof MARKER_COLORS

export function parcelMarkerStatus(parcel: DashboardParcel): ParcelMarkerStatus {
  if (parcel.issue_trees > 0) return 'issue'
  if (parcel.monitoring_trees > 0 || parcel.open_cases > 0) return 'monitoring'
  return 'healthy'
}

function createMarkerIcon(status: ParcelMarkerStatus) {
  const color = MARKER_COLORS[status]
  return L.divIcon({
    className: 'agrotwin-map-marker',
    html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:${color};border:2px solid #fff;box-shadow:0 1px 6px rgba(16,36,26,0.35)"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -8],
  })
}

function MapResizeHandler({ containerRef }: { containerRef: RefObject<HTMLDivElement | null> }) {
  const map = useMap()

  useEffect(() => {
    const container = containerRef.current
    if (!container) return undefined

    const refresh = () => {
      map.invalidateSize()
    }
    const timeout = window.setTimeout(refresh, 0)
    const observer = new ResizeObserver(refresh)
    observer.observe(container)

    return () => {
      window.clearTimeout(timeout)
      observer.disconnect()
    }
  }, [containerRef, map])

  return null
}

function ParcelMarker({ parcel }: { parcel: DashboardParcel }) {
  const coords = parcelCoordinates(parcel)
  if (!coords) return null
  const status = parcelMarkerStatus(parcel)
  const icon = createMarkerIcon(status)

  return (
    <Marker position={[coords.lat, coords.lng]} icon={icon}>
      <Popup>
        <div className="min-w-[180px] space-y-2 text-sm">
          <p className="font-semibold text-foreground">{parcel.name}</p>
          {parcel.code === parcel.name ? null : <p className="text-xs text-muted-foreground">{parcel.code}</p>}
          <p className="text-xs text-muted-foreground">
            {formatNumber(parcel.tree_count)} stabala
            {parcel.area_hectares ? ` · ${Number(parcel.area_hectares).toFixed(2)} ha` : ''}
          </p>
          <Link to={`/orchard/${parcel.id}`} className="inline-block text-xs font-medium text-primary hover:underline">
            Otvori zasad
          </Link>
        </div>
      </Popup>
    </Marker>
  )
}

type ParcelsMapProps = {
  className?: string
  parcels: DashboardParcel[]
}

export function ParcelsMap({ className, parcels }: ParcelsMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isMounted, setIsMounted] = useState(false)
  const located = useMemo(
    () => parcels.filter((parcel) => parcelCoordinates(parcel) !== null),
    [parcels],
  )

  useEffect(() => {
    setIsMounted(true)
  }, [])

  return (
    <div ref={containerRef} className={cn('agrotwin-map-root relative h-full overflow-hidden rounded-2xl', className)}>
      {isMounted ? (
        <MapContainer
          center={SERBIA_CENTER}
          zoom={7}
          minZoom={6}
          maxZoom={16}
          scrollWheelZoom={false}
          className="h-full w-full"
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapResizeHandler containerRef={containerRef} />
          {located.map((parcel) => (
            <ParcelMarker key={parcel.id} parcel={parcel} />
          ))}
        </MapContainer>
      ) : (
        <div className="flex h-full items-center justify-center bg-muted/60">
          <p className="text-sm text-muted-foreground">Učitavanje mape…</p>
        </div>
      )}

      {parcels.length > 0 && located.length === 0 ? (
        <div className="pointer-events-none absolute inset-0 z-[400] flex items-center justify-center p-6">
          <p className="rounded-xl border border-border bg-card/90 px-4 py-3 text-center text-sm text-muted-foreground">
            Unesite Google Maps link na parceli da se zasad prikaže na mapi.
          </p>
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[500] p-3">
        <div className="pointer-events-auto inline-flex flex-wrap gap-2 rounded-xl border border-border/70 bg-card/95 px-3 py-2 text-xs shadow-md">
          <LegendDot color={MARKER_COLORS.healthy} label="Uredno" />
          <LegendDot color={MARKER_COLORS.monitoring} label="Praćenje" />
          <LegendDot color={MARKER_COLORS.issue} label="Problem" />
        </div>
      </div>
    </div>
  )
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}
