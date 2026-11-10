import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  CircleMarker,
  ImageOverlay,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import type { EditorMode, MapEditorRowDraft, MapEditorTreeDraft } from '@/features/map-editor/types'
import { STRETCH, indexLegendGradient } from '@/features/orchard/monitoring/ndviScale'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'
export type BasemapId = 'osm' | 'esri'

export type MapViewSnapshot = {
  center: [number, number]
  zoom: number
}

type Props = {
  mode: EditorMode
  basemap: BasemapId
  draftRing: [number, number][] // [lat, lng]
  committedBoundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  /** When true, hide saved boundary so user starts from a blank map. */
  hideCommittedBoundary?: boolean
  mapCenter?: [number, number] | null
  /** When this changes, map flies to the new center (wizard location step). */
  flyTo?: [number, number] | null
  flyToZoom?: number
  initialZoom?: number
  /** One-shot fit to an existing parcel ring after editor hydrate. */
  fitRingOnce?: [number, number][] | null
  onFitRingDone?: () => void
  /**
   * Exact view to freeze while drawing boundary (captured before step change).
   * Prevents layout/resize from shifting the parcel out of frame.
   */
  lockedView?: MapViewSnapshot | null
  /** Fires whenever the user-driven map view settles (pan/zoom/fly). */
  onViewChange?: (view: MapViewSnapshot) => void
  rows: MapEditorRowDraft[]
  trees: MapEditorTreeDraft[]
  varietyColors: Map<string, string>
  varietyFilter: string | null
  paintVariety: string | null
  showBoundary: boolean
  showRows: boolean
  showTrees: boolean
  /** Drag orange vertices to reshape boundary (planting / boundary / review). */
  allowVertexEdit?: boolean
  /** Show clickable edges for parallel-row reference side. */
  showOrientationEdges?: boolean
  indexOverlayUrl: string | null
  indexBounds: [[number, number], [number, number]] | null
  indexOpacity: number
  activeIndexLabel: string | null
  orientationPreview: [[number, number], [number, number]] | null
  selectedEdgeIndex: number | null
  /** Highlight edge while hovering the matching margin field in the sidebar. */
  highlightEdgeIndex?: number | null
  measurePoints: [number, number][]
  cursorLatLng: { lat: number; lng: number } | null
  onCursorMove: (pos: { lat: number; lng: number } | null) => void
  onMapClick: (lat: number, lng: number) => void
  /** Commit a full edited ring (after vertex drag ends). */
  onRingCommit: (ring: [number, number][]) => void
  onSelectEdge: (edgeIndex: number) => void
  onTreeSelect: (draftId: string) => void
  onRowSelect: (draftId: string) => void
  /** Drag either endpoint of a row to move/rotate it. */
  allowRowEndpointEdit?: boolean
  onRowEndpointCommit?: (
    rowDraftId: string,
    segmentIndex: number,
    endIndex: 0 | 1,
    lat: number,
    lng: number,
  ) => void
  onRowEndpointLive?: (
    rowDraftId: string,
    segmentIndex: number,
    endIndex: 0 | 1,
    lat: number,
    lng: number,
  ) => void
  /**
   * Drag trees only along their row line. Parent must snap lat/lng via onTreeSlide.
   */
  allowTreeSlideAlongRow?: boolean
  onTreeSlide?: (treeDraftId: string, lat: number, lng: number, commit: boolean) => void
  /** Double-click a tree to remove it (review step). */
  onTreeDelete?: (treeDraftId: string) => void
  /**
   * When true, map clicks still fire in `select_tree` mode (e.g. add seedling on review).
   */
  allowSelectTreeMapClick?: boolean
  /** Highlight trees belonging to this row number (review step). */
  highlightRowNumber?: number | null
  selectedTreeId: string | null
  selectedRowId: string | null
  className?: string
  children?: ReactNode
}

/** Global pointer tracking while a tree is being slid along its row. */
function TreeSlideMapBridge({
  activeRef,
  movedRef,
  onSlide,
}: {
  activeRef: { current: string | null }
  movedRef: { current: boolean }
  onSlide: (treeDraftId: string, lat: number, lng: number, commit: boolean) => void
}) {
  const map = useMap()
  const onSlideRef = useRef(onSlide)
  onSlideRef.current = onSlide
  useEffect(() => {
    const onMove = (ev: PointerEvent) => {
      const id = activeRef.current
      if (!id) return
      movedRef.current = true
      const latlng = map.mouseEventToLatLng(ev as unknown as MouseEvent)
      onSlideRef.current(id, latlng.lat, latlng.lng, false)
    }
    const onUp = (ev: PointerEvent) => {
      const id = activeRef.current
      if (!id) return
      const latlng = map.mouseEventToLatLng(ev as unknown as MouseEvent)
      onSlideRef.current(id, latlng.lat, latlng.lng, true)
      activeRef.current = null
      map.dragging.enable()
      map.touchZoom.enable()
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [map, activeRef, movedRef])
  return null
}

function lineCoordsFromGeometry(geom: GeoJSON.LineString | GeoJSON.MultiLineString): [number, number][][] {
  const toLatLng = (line: number[][]): [number, number][] => {
    const out: [number, number][] = []
    for (const c of line) {
      if (c.length < 2) continue
      out.push([Number(c[1]), Number(c[0])])
    }
    return out
  }
  if (geom.type === 'LineString') {
    return [toLatLng(geom.coordinates)]
  }
  return geom.coordinates.map((line) => toLatLng(line))
}

/**
 * Draggable handles at both ends of each row segment (move + slight rotate).
 */
function RowEndpointEditor({
  rows,
  selectedRowId,
  enabled,
  onLive,
  onCommit,
}: {
  rows: MapEditorRowDraft[]
  selectedRowId: string | null
  enabled: boolean
  onLive: (rowDraftId: string, segmentIndex: number, endIndex: 0 | 1, lat: number, lng: number) => void
  onCommit: (rowDraftId: string, segmentIndex: number, endIndex: 0 | 1, lat: number, lng: number) => void
}) {
  const map = useMap()
  const drag = useRef<{
    rowDraftId: string
    segmentIndex: number
    endIndex: 0 | 1
    lat: number
    lng: number
  } | null>(null)
  const onLiveRef = useRef(onLive)
  const onCommitRef = useRef(onCommit)
  onLiveRef.current = onLive
  onCommitRef.current = onCommit

  const finish = useRef(() => {
    const d = drag.current
    if (!d) return
    drag.current = null
    map.dragging.enable()
    map.touchZoom.enable()
    map.doubleClickZoom.enable()
    map.boxZoom.enable()
    map.keyboard.enable()
    onCommitRef.current(d.rowDraftId, d.segmentIndex, d.endIndex, d.lat, d.lng)
  })
  finish.current = () => {
    const d = drag.current
    if (!d) return
    drag.current = null
    map.dragging.enable()
    map.touchZoom.enable()
    map.doubleClickZoom.enable()
    map.boxZoom.enable()
    map.keyboard.enable()
    onCommitRef.current(d.rowDraftId, d.segmentIndex, d.endIndex, d.lat, d.lng)
  }

  useEffect(() => {
    const onMove = (ev: PointerEvent) => {
      if (!drag.current) return
      const latlng = map.mouseEventToLatLng(ev as unknown as MouseEvent)
      drag.current = { ...drag.current, lat: latlng.lat, lng: latlng.lng }
      onLiveRef.current(
        drag.current.rowDraftId,
        drag.current.segmentIndex,
        drag.current.endIndex,
        latlng.lat,
        latlng.lng,
      )
    }
    const onUp = () => finish.current()
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [map])

  if (!enabled) return null

  const handles: Array<{
    key: string
    rowDraftId: string
    segmentIndex: number
    endIndex: 0 | 1
    pos: [number, number]
    selected: boolean
  }> = []

  for (const row of rows) {
    const lines = lineCoordsFromGeometry(row.geometry)
    lines.forEach((line, segIdx) => {
      if (line.length < 2) return
      const start = line[0]!
      const end = line[line.length - 1]!
      const selected = selectedRowId === row.draft_id
      handles.push({
        key: `${row.draft_id}-${segIdx}-0`,
        rowDraftId: row.draft_id,
        segmentIndex: segIdx,
        endIndex: 0,
        pos: start,
        selected,
      })
      handles.push({
        key: `${row.draft_id}-${segIdx}-1`,
        rowDraftId: row.draft_id,
        segmentIndex: segIdx,
        endIndex: 1,
        pos: end,
        selected,
      })
    })
  }

  return (
    <>
      {handles.map((h) => (
        <CircleMarker
          key={h.key}
          center={h.pos}
          radius={h.selected ? 9 : 7}
          bubblingMouseEvents={false}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: h.selected ? '#f97316' : '#38bdf8',
            fillOpacity: 1,
            className: 'map-editor-row-endpoint',
          }}
          eventHandlers={{
            mousedown: (e) => {
              L.DomEvent.preventDefault(e.originalEvent)
              L.DomEvent.stopPropagation(e.originalEvent)
              L.DomEvent.stop(e)
              drag.current = {
                rowDraftId: h.rowDraftId,
                segmentIndex: h.segmentIndex,
                endIndex: h.endIndex,
                lat: h.pos[0],
                lng: h.pos[1],
              }
              map.dragging.disable()
              map.touchZoom.disable()
              map.doubleClickZoom.disable()
              map.boxZoom.disable()
              map.keyboard.disable()
            },
            click: (e) => {
              L.DomEvent.preventDefault(e.originalEvent)
              L.DomEvent.stopPropagation(e.originalEvent)
              L.DomEvent.stop(e)
            },
          }}
        >
          <Tooltip direction="top" offset={[0, -6]} opacity={0.9}>
            Red · {h.endIndex === 0 ? tr('početak') : 'kraj'} · prevuci
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
}

function FlyToCenter({
  target,
  zoom,
}: {
  target: [number, number] | null | undefined
  zoom?: number
}) {
  const map = useMap()
  const last = useRef<string | null>(null)
  useEffect(() => {
    if (!target) return
    const key = `${target[0].toFixed(6)},${target[1].toFixed(6)}@${zoom ?? 20}`
    if (last.current === key) return
    last.current = key
    const maxZ = map.getMaxZoom()
    const targetZoom = Math.min(zoom ?? 20, maxZ)
    map.flyTo(target, targetZoom, { duration: 0.85 })
  }, [map, target, zoom])
  return null
}

/** Google satellite — reliable high-zoom coverage in Serbia (Esri often serves empty placeholders). */
const SATELLITE_URL = 'https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
const SATELLITE_SUBDOMAINS = '0123'
const OSM_URL = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'

const BOUNDARY_STYLE: L.PathOptions = {
  color: '#eab308',
  weight: 3,
  fillColor: '#eab308',
  fillOpacity: 0.08,
}

const DRAFT_STYLE: L.PathOptions = {
  color: '#f59e0b',
  weight: 2.5,
  dashArray: '6 4',
  fillColor: '#f59e0b',
  fillOpacity: 0.12,
}

/**
 * Fit only a saved committed boundary once. Never recenters on mapCenter
 * (FlyToCenter handles search) and never fits the draft ring while drawing.
 */
function FitBounds({
  boundary,
  enabled,
}: {
  boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
  enabled: boolean
}) {
  const map = useMap()
  const fitted = useRef(false)
  useEffect(() => {
    if (!enabled || fitted.current || !boundary) return
    const pts: [number, number][] = []
    if (boundary.type === 'Polygon') {
      for (const c of boundary.coordinates[0] ?? []) {
        if (c.length < 2) continue
        pts.push([Number(c[1]), Number(c[0])])
      }
    } else if (boundary.type === 'MultiPolygon') {
      for (const poly of boundary.coordinates) {
        for (const c of poly[0] ?? []) {
          if (c.length < 2) continue
          pts.push([Number(c[1]), Number(c[0])])
        }
      }
    }
    if (pts.length < 2) return
    map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 18 })
    fitted.current = true
  }, [map, boundary, enabled])
  return null
}

/** One-shot fit after loading an existing parcel into the wizard. */
function FitRingOnce({
  ring,
  onDone,
}: {
  ring: [number, number][] | null | undefined
  onDone?: () => void
}) {
  const map = useMap()
  const doneKey = useRef<string | null>(null)
  useEffect(() => {
    if (!ring || ring.length < 3) return
    const key = `${ring.length}:${ring[0]?.[0]?.toFixed(5)},${ring[0]?.[1]?.toFixed(5)}`
    if (doneKey.current === key) return
    doneKey.current = key
    requestAnimationFrame(() => {
      map.invalidateSize()
      map.fitBounds(L.latLngBounds(ring), { padding: [48, 48], maxZoom: 18, animate: false })
      onDone?.()
    })
  }, [map, ring, onDone])
  return null
}

function ViewReporter({
  enabled,
  onViewChange,
}: {
  enabled: boolean
  onViewChange?: (view: MapViewSnapshot) => void
}) {
  const map = useMap()
  useEffect(() => {
    if (!enabled || !onViewChange) return
    const report = () => {
      const c = map.getCenter()
      onViewChange({ center: [c.lat, c.lng], zoom: map.getZoom() })
    }
    report()
    map.on('moveend', report)
    map.on('zoomend', report)
    return () => {
      map.off('moveend', report)
      map.off('zoomend', report)
    }
  }, [map, enabled, onViewChange])
  return null
}

/**
 * Hard-freeze center + zoom while drawing/editing boundary.
 * Prefer `lockedView` captured before the step change so layout resize cannot shift framing.
 */
function LockMapView({
  locked,
  lockedView,
}: {
  locked: boolean
  lockedView?: MapViewSnapshot | null
}) {
  const map = useMap()
  const frozen = useRef<{ lat: number; lng: number; zoom: number } | null>(null)
  const restoring = useRef(false)

  useEffect(() => {
    if (!locked) {
      frozen.current = null
      map.dragging.enable()
      map.boxZoom.enable()
      map.keyboard.enable()
      map.doubleClickZoom.enable()
      map.touchZoom.enable()
      map.scrollWheelZoom.enable()
      return
    }

    const applyFrozen = (lat: number, lng: number, zoom: number) => {
      frozen.current = { lat, lng, zoom }
      restoring.current = true
      map.setView([lat, lng], zoom, { animate: false })
      restoring.current = false
    }

    if (lockedView) {
      applyFrozen(lockedView.center[0], lockedView.center[1], lockedView.zoom)
    } else {
      const c = map.getCenter()
      applyFrozen(c.lat, c.lng, map.getZoom())
    }

    map.dragging.disable()
    map.boxZoom.disable()
    map.keyboard.disable()
    map.doubleClickZoom.disable()
    map.touchZoom.disable()
    map.scrollWheelZoom.disable()

    // After layout settles (sidebar/toolbar), keep the same geographic framing.
    const t1 = window.setTimeout(() => {
      map.invalidateSize({ pan: false })
      const f = frozen.current
      if (f) applyFrozen(f.lat, f.lng, f.zoom)
    }, 0)
    const t2 = window.setTimeout(() => {
      map.invalidateSize({ pan: false })
      const f = frozen.current
      if (f) applyFrozen(f.lat, f.lng, f.zoom)
    }, 50)

    const reinstate = () => {
      const f = frozen.current
      if (!f || restoring.current) return
      const cur = map.getCenter()
      if (
        Math.abs(cur.lat - f.lat) > 1e-9 ||
        Math.abs(cur.lng - f.lng) > 1e-9 ||
        map.getZoom() !== f.zoom
      ) {
        applyFrozen(f.lat, f.lng, f.zoom)
      }
    }

    map.on('move', reinstate)
    map.on('moveend', reinstate)
    map.on('zoom', reinstate)
    map.on('zoomend', reinstate)

    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      map.off('move', reinstate)
      map.off('moveend', reinstate)
      map.off('zoom', reinstate)
      map.off('zoomend', reinstate)
      map.dragging.enable()
      map.boxZoom.enable()
      map.keyboard.enable()
      map.doubleClickZoom.enable()
      map.touchZoom.enable()
      map.scrollWheelZoom.enable()
    }
  }, [map, locked, lockedView])

  return null
}

/**
 * Vertex editing via map pointer events (not Marker.draggable).
 * Leaflet marker drag is unreliable under react-leaflet re-renders.
 */
function VertexEditor({
  ring,
  editable,
  keepMapLocked,
  onLiveChange,
  onCommit,
}: {
  ring: [number, number][]
  editable: boolean
  /** When true, do not re-enable map.dragging after vertex drag (parent locks pan). */
  keepMapLocked?: boolean
  onLiveChange: (ring: [number, number][]) => void
  onCommit: (ring: [number, number][]) => void
}) {
  const map = useMap()
  const dragIndex = useRef<number | null>(null)
  const ringRef = useRef(ring)
  ringRef.current = ring
  const keepLockedRef = useRef(keepMapLocked)
  keepLockedRef.current = keepMapLocked

  const finishDrag = useRef(() => {
    if (dragIndex.current == null) return
    dragIndex.current = null
    if (!keepLockedRef.current) {
      map.dragging.enable()
      map.touchZoom.enable()
      map.doubleClickZoom.enable()
      map.boxZoom.enable()
      map.keyboard.enable()
    }
    onCommit(ringRef.current.map((p) => [p[0], p[1]] as [number, number]))
  })
  finishDrag.current = () => {
    if (dragIndex.current == null) return
    dragIndex.current = null
    if (!keepLockedRef.current) {
      map.dragging.enable()
      map.touchZoom.enable()
      map.doubleClickZoom.enable()
      map.boxZoom.enable()
      map.keyboard.enable()
    }
    onCommit(ringRef.current.map((p) => [p[0], p[1]] as [number, number]))
  }

  const onLiveChangeRef = useRef(onLiveChange)
  onLiveChangeRef.current = onLiveChange

  const moveTo = (lat: number, lng: number) => {
    if (dragIndex.current == null) return
    const i = dragIndex.current
    const next = ringRef.current.map(
      (p, j) => (j === i ? ([lat, lng] as [number, number]) : p),
    )
    ringRef.current = next
    onLiveChangeRef.current(next)
  }

  useEffect(() => {
    const onMove = (ev: PointerEvent) => {
      if (dragIndex.current == null) return
      const latlng = map.mouseEventToLatLng(ev as unknown as MouseEvent)
      moveTo(latlng.lat, latlng.lng)
    }
    const onUp = () => finishDrag.current()
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [map])

  useMapEvents({
    mousemove(e) {
      if (dragIndex.current == null) return
      moveTo(e.latlng.lat, e.latlng.lng)
    },
    mouseup() {
      finishDrag.current()
    },
  })

  return (
    <>
      {ring.map((pt, index) => (
        <CircleMarker
          key={`vertex-${index}`}
          center={pt}
          radius={editable ? 12 : 6}
          bubblingMouseEvents={false}
          pathOptions={{
            color: '#ffffff',
            weight: 3,
            fillColor: '#f59e0b',
            fillOpacity: 1,
            opacity: 1,
            className: 'map-editor-vertex-handle',
          }}
          eventHandlers={
            editable
              ? {
                  mousedown: (e) => {
                    L.DomEvent.preventDefault(e.originalEvent)
                    L.DomEvent.stopPropagation(e.originalEvent)
                    L.DomEvent.stop(e)
                    dragIndex.current = index
                    map.dragging.disable()
                    map.touchZoom.disable()
                    map.doubleClickZoom.disable()
                    map.boxZoom.disable()
                    map.keyboard.disable()
                  },
                  click: (e) => {
                    L.DomEvent.preventDefault(e.originalEvent)
                    L.DomEvent.stopPropagation(e.originalEvent)
                    L.DomEvent.stop(e)
                  },
                }
              : {
                  click: (e) => L.DomEvent.stop(e),
                }
          }
        >
          <Tooltip direction="top" offset={[0, -8]} opacity={0.9}>
            Teme {index + 1}
            {editable ? tr(' · drži i prevuci') : ''}
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
}

function MapEvents({
  mode,
  onClick,
  onCursorMove,
  allowSelectTreeMapClick = false,
}: {
  mode: EditorMode
  onClick: (lat: number, lng: number) => void
  onCursorMove: (pos: { lat: number; lng: number } | null) => void
  allowSelectTreeMapClick?: boolean
}) {
  useMapEvents({
    click(e) {
      if (mode === 'select_tree' && allowSelectTreeMapClick) {
        onClick(e.latlng.lat, e.latlng.lng)
        return
      }
      if (
        mode === 'select' ||
        mode === 'inspect_index' ||
        mode === 'edit_boundary' ||
        mode === 'assign_variety' ||
        mode === 'select_row' ||
        mode === 'select_tree'
      ) {
        return
      }
      onClick(e.latlng.lat, e.latlng.lng)
    },
    mousemove(e) {
      onCursorMove({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
    mouseout() {
      onCursorMove(null)
    },
  })
  return null
}

function ScaleBar() {
  const map = useMap()
  useEffect(() => {
    const control = L.control.scale({ imperial: false, metric: true, position: 'bottomleft' })
    control.addTo(map)
    return () => {
      control.remove()
    }
  }, [map])
  return null
}

export function MapEditorCanvas({
  mode,
  basemap,
  draftRing,
  committedBoundary,
  hideCommittedBoundary = false,
  mapCenter = null,
  flyTo = null,
  flyToZoom = 20,
  initialZoom = 20,
  fitRingOnce = null,
  onFitRingDone,
  lockedView = null,
  onViewChange,
  rows,
  trees,
  varietyColors,
  varietyFilter,
  paintVariety,
  showBoundary,
  showRows,
  showTrees,
  allowVertexEdit = false,
  showOrientationEdges = false,
  indexOverlayUrl,
  indexBounds,
  indexOpacity,
  activeIndexLabel,
  orientationPreview,
  selectedEdgeIndex,
  highlightEdgeIndex = null,
  measurePoints,
  cursorLatLng,
  onCursorMove,
  onMapClick,
  onRingCommit,
  onSelectEdge,
  onTreeSelect,
  onRowSelect,
  allowRowEndpointEdit = false,
  onRowEndpointCommit,
  onRowEndpointLive,
  allowTreeSlideAlongRow = false,
  onTreeSlide,
  onTreeDelete,
  allowSelectTreeMapClick = false,
  highlightRowNumber = null,
  selectedTreeId,
  selectedRowId,
  className,
  children,
}: Props) {
  const treeDragId = useRef<string | null>(null)
  const treeDragMoved = useRef(false)
  const [fullscreenEl, setFullscreenEl] = useState<HTMLDivElement | null>(null)
  const [liveRing, setLiveRing] = useState<[number, number][] | null>(null)
  // Stable initial center — never follow draftRing[0] (that recenters on first vertex).
  const center = useMemo<[number, number]>(() => {
    if (mapCenter) return mapCenter
    if (!hideCommittedBoundary && committedBoundary?.type === 'Polygon') {
      const c = committedBoundary.coordinates[0]?.[0]
      if (c && c.length >= 2) return [Number(c[1]), Number(c[0])]
    }
    return [44.8176, 20.4633]
  }, [committedBoundary, mapCenter, hideCommittedBoundary])

  const viewLocked = mode === 'draw_boundary' || mode === 'edit_boundary'

  const displayRing = liveRing ?? draftRing
  const closedDraft: [number, number][] =
    displayRing.length >= 3 && displayRing[0] ? [...displayRing, displayRing[0]] : displayRing

  const visibleTrees = useMemo(() => {
    if (!varietyFilter) return trees
    return trees.filter((t) => (t.variety ?? '') === varietyFilter)
  }, [trees, varietyFilter])

  const showSavedGhost = showBoundary && !hideCommittedBoundary && committedBoundary && draftRing.length === 0

  return (
    <div
      ref={setFullscreenEl}
      className={cn(
        'agrotwin-map-root relative h-full min-h-[420px] w-full overflow-hidden rounded-lg border border-border',
        viewLocked && 'agrotwin-map-view-locked',
        className,
      )}
    >
      <MapContainer
        center={center}
        zoom={initialZoom}
        maxZoom={20}
        minZoom={5}
        className="h-full w-full bg-muted"
        zoomControl={false}
        attributionControl
        preferCanvas={false}
      >
        <TileLayer
          key={basemap}
          url={basemap === 'esri' ? SATELLITE_URL : OSM_URL}
          subdomains={basemap === 'esri' ? SATELLITE_SUBDOMAINS : 'abc'}
          attribution={
            basemap === 'esri'
              ? 'Imagery © Google'
              : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          }
          maxZoom={basemap === 'esri' ? 20 : 19}
        />
        <ZoomControl position="topright" />
        <ScaleBar />
        <FitBounds
          boundary={hideCommittedBoundary ? null : committedBoundary}
          enabled={!viewLocked}
        />
        <FitRingOnce ring={fitRingOnce} onDone={onFitRingDone} />
        {!viewLocked ? <FlyToCenter target={flyTo} zoom={flyToZoom} /> : null}
        <ViewReporter enabled={!viewLocked} onViewChange={onViewChange} />
        <LockMapView locked={viewLocked} lockedView={lockedView} />
        <MapEvents
          mode={mode}
          onClick={onMapClick}
          onCursorMove={onCursorMove}
          allowSelectTreeMapClick={allowSelectTreeMapClick}
        />

        {indexOverlayUrl && indexBounds ? (
          <ImageOverlay url={indexOverlayUrl} bounds={indexBounds} opacity={indexOpacity} zIndex={200} />
        ) : null}

        {showSavedGhost ? (
          <Polygon
            positions={(() => {
              const ring =
                committedBoundary!.type === 'Polygon'
                  ? (committedBoundary!.coordinates[0] ?? [])
                  : (committedBoundary!.coordinates[0]?.[0] ?? [])
              const positions: [number, number][] = []
              for (const c of ring) {
                if (c.length < 2) continue
                positions.push([Number(c[1]), Number(c[0])])
              }
              return positions
            })()}
            pathOptions={BOUNDARY_STYLE}
          />
        ) : null}

        {/* Subtle outline when picking edges / editing vertices (no heavy filled rectangle). */}
        {showBoundary && closedDraft.length >= 2 && (showOrientationEdges || allowVertexEdit) && mode !== 'draw_boundary' ? (
          <Polygon
            positions={closedDraft}
            pathOptions={{
              color: '#eab308',
              weight: 1.5,
              dashArray: '4 4',
              fillColor: '#eab308',
              fillOpacity: 0.04,
              interactive: false,
            }}
          />
        ) : null}

        {showBoundary && closedDraft.length >= 2 && !showOrientationEdges && !allowVertexEdit ? (
          <Polygon
            positions={closedDraft}
            pathOptions={{
              ...(mode === 'draw_boundary' || mode === 'edit_boundary' ? DRAFT_STYLE : BOUNDARY_STYLE),
              interactive: false,
            }}
          />
        ) : null}

        {showBoundary && closedDraft.length >= 2 && mode === 'draw_boundary' ? (
          <Polygon
            positions={closedDraft}
            pathOptions={{
              ...DRAFT_STYLE,
              interactive: false,
            }}
          />
        ) : null}

        {(allowVertexEdit || mode === 'draw_boundary' || mode === 'edit_boundary') && displayRing.length > 0 ? (
          <VertexEditor
            ring={displayRing}
            editable={allowVertexEdit || mode === 'draw_boundary' || mode === 'edit_boundary'}
            keepMapLocked={mode === 'draw_boundary' || mode === 'edit_boundary'}
            onLiveChange={(next) => setLiveRing(next)}
            onCommit={(next) => {
              setLiveRing(null)
              onRingCommit(next)
            }}
          />
        ) : null}

        {(showOrientationEdges || mode === 'row_orientation') && draftRing.length >= 2
          ? draftRing.map((pt, index) => {
              const next = draftRing[(index + 1) % draftRing.length]
              if (!next) return null
              const selected = selectedEdgeIndex === index
              const highlighted = highlightEdgeIndex === index
              const mid: [number, number] = [(pt[0] + next[0]) / 2, (pt[1] + next[1]) / 2]
              const label = String(index + 1)
              const badge = L.divIcon({
                className: 'map-editor-edge-badge',
                html: `<div style="
                  display:flex;align-items:center;justify-content:center;
                  min-width:20px;height:20px;padding:0 5px;border-radius:999px;
                  background:${selected ? '#0891b2' : highlighted ? '#f59e0b' : 'rgba(15,23,42,0.88)'};
                  color:#fff;font:700 11px/1 Montserrat,system-ui,sans-serif;
                  border:2px solid ${selected || highlighted ? '#fff' : 'rgba(255,255,255,0.75)'};
                  box-shadow:0 1px 3px rgba(0,0,0,0.35);
                ">${label}</div>`,
                iconSize: [22, 22],
                iconAnchor: [11, 11],
              })
              return [
                <Polyline
                  key={`edge-${index}`}
                  positions={[pt, next]}
                  pathOptions={{
                    color: selected ? '#06b6d4' : highlighted ? '#f59e0b' : '#eab308',
                    weight: selected || highlighted ? 6 : 2.5,
                    opacity: selected || highlighted ? 1 : 0.55,
                    dashArray: selected || highlighted ? undefined : '6 5',
                  }}
                  eventHandlers={{
                    click: (e) => {
                      L.DomEvent.stopPropagation(e)
                      onSelectEdge(index)
                    },
                    mouseover: (e) => {
                      const layer = e.target as L.Polyline
                      if (!selected && !highlighted) {
                        layer.setStyle({ weight: 4, color: '#fbbf24', opacity: 0.9 })
                      }
                    },
                    mouseout: (e) => {
                      const layer = e.target as L.Polyline
                      if (!selected && !highlighted) {
                        layer.setStyle({
                          weight: 2.5,
                          color: '#eab308',
                          opacity: 0.55,
                          dashArray: '6 5',
                        })
                      }
                    },
                  }}
                >
                  <Tooltip sticky>
                    Stranica {index + 1}
                    {selected
                      ? tr(' · referentna (redovi paralelni)')
                      : ' · klik = referentna stranica'}
                  </Tooltip>
                </Polyline>,
                <Marker
                  key={`edge-label-${index}`}
                  position={mid}
                  icon={badge}
                  interactive={false}
                  zIndexOffset={selected || highlighted ? 600 : 450}
                />,
              ]
            })
          : null}

        {measurePoints.length >= 1 ? (
          <Polyline
            positions={measurePoints}
            pathOptions={{ color: '#a78bfa', weight: 2, dashArray: '4 4' }}
          />
        ) : null}

        {showRows &&
          rows.map((row) => {
            const rowVariety = row.default_variety
            const rowColor =
              selectedRowId === row.draft_id
                ? '#f97316'
                : rowVariety
                  ? (varietyColors.get(rowVariety) ?? '#38bdf8')
                  : mode === 'assign_variety' && paintVariety
                    ? '#94a3b8'
                    : '#38bdf8'
            return lineCoordsFromGeometry(row.geometry).map((line, i) => (
              <Polyline
                key={`${row.draft_id}-${i}`}
                positions={line}
                pathOptions={{
                  color: rowColor,
                  weight: selectedRowId === row.draft_id || (mode === 'assign_variety' && paintVariety) ? 4 : 2.5,
                  opacity: 0.95,
                }}
                eventHandlers={{
                  click: (e) => {
                    L.DomEvent.stopPropagation(e)
                    onRowSelect(row.draft_id)
                  },
                }}
              >
                <Tooltip sticky>
                  Red {row.row_number}
                  {row.segment_index > 0 ? ` · seg ${row.segment_index + 1}` : ''}
                  {rowVariety ? ` · ${rowVariety}` : tr(' · bez sorte')}
                  {mode === 'assign_variety' && paintVariety ? ` → klik = ${paintVariety}` : ''}
                  {allowRowEndpointEdit ? tr(' · prevuci plave tačke na krajevima') : ''}
                </Tooltip>
              </Polyline>
            ))
          })}

        {allowRowEndpointEdit && onRowEndpointCommit ? (
          <RowEndpointEditor
            rows={rows}
            selectedRowId={selectedRowId}
            enabled={allowRowEndpointEdit}
            onLive={(rowDraftId, segmentIndex, endIndex, lat, lng) => {
              onRowEndpointLive?.(rowDraftId, segmentIndex, endIndex, lat, lng)
            }}
            onCommit={(rowDraftId, segmentIndex, endIndex, lat, lng) => {
              onRowEndpointCommit(rowDraftId, segmentIndex, endIndex, lat, lng)
            }}
          />
        ) : null}

        {/* Faint guide for the active review row — slide/add snap to this axis. */}
        {allowTreeSlideAlongRow && highlightRowNumber != null
          ? rows
              .filter((r) => r.row_number === highlightRowNumber)
              .flatMap((row) =>
                lineCoordsFromGeometry(row.geometry).map((line, i) => (
                  <Polyline
                    key={`review-guide-${row.draft_id}-${i}`}
                    positions={line}
                    pathOptions={{
                      color: '#0ea5e9',
                      weight: 2,
                      opacity: 0.35,
                      dashArray: '6 8',
                      interactive: false,
                    }}
                  />
                )),
              )
          : null}

        {showTrees &&
          visibleTrees.map((tree) => {
            const onActiveRow =
              highlightRowNumber == null || tree.row_number === highlightRowNumber
            const color = tree.variety
              ? varietyColors.get(tree.variety) ?? '#94a3b8'
              : onActiveRow
                ? '#0ea5e9'
                : '#94a3b8'
            const selected = selectedTreeId === tree.draft_id
            const dimmed = highlightRowNumber != null && tree.row_number !== highlightRowNumber
            return (
              <CircleMarker
                key={tree.draft_id}
                center={[tree.latitude, tree.longitude]}
                radius={selected ? 8 : tree.variety ? 5 : 5}
                pathOptions={{
                  color: selected ? '#fff' : color,
                  fillColor: color,
                  fillOpacity: dimmed ? 0.25 : tree.variety ? 0.95 : 0.75,
                  weight: selected ? 2.5 : 1,
                  dashArray: tree.manually_placed ? '2 2' : undefined,
                }}
                eventHandlers={{
                  mousedown: (e) => {
                    if (!allowTreeSlideAlongRow || !onTreeSlide) return
                    L.DomEvent.preventDefault(e.originalEvent)
                    L.DomEvent.stopPropagation(e.originalEvent)
                    L.DomEvent.stop(e)
                    treeDragId.current = tree.draft_id
                    treeDragMoved.current = false
                    onTreeSelect(tree.draft_id)
                    const map = e.target._map as L.Map | undefined
                    map?.dragging.disable()
                    map?.touchZoom.disable()
                  },
                  click: (e) => {
                    L.DomEvent.stopPropagation(e)
                    if (mode === 'assign_variety') {
                      onRowSelect(tree.row_draft_id)
                      return
                    }
                    if (treeDragMoved.current) {
                      treeDragMoved.current = false
                      return
                    }
                    onTreeSelect(tree.draft_id)
                  },
                  dblclick: (e) => {
                    if (!allowTreeSlideAlongRow || !onTreeDelete) return
                    L.DomEvent.stopPropagation(e)
                    L.DomEvent.preventDefault(e.originalEvent)
                    onTreeDelete(tree.draft_id)
                  },
                }}
              >
                <Tooltip direction="top">
                  R{tree.row_number}-T{tree.tree_number}
                  {tree.variety ? ` · ${tree.variety}` : tr(' · bez sorte')}
                  {allowTreeSlideAlongRow
                    ? tr(' · prevuci duž reda · dvoklik = obriši')
                    : ''}
                </Tooltip>
              </CircleMarker>
            )
          })}

        {allowTreeSlideAlongRow && onTreeSlide ? (
          <TreeSlideMapBridge
            activeRef={treeDragId}
            movedRef={treeDragMoved}
            onSlide={(id, lat, lng, commit) => onTreeSlide(id, lat, lng, commit)}
          />
        ) : null}
      </MapContainer>

      <div className="pointer-events-none absolute left-3 top-3 z-[1000] flex flex-col gap-1 rounded-md bg-background/90 px-2 py-1.5 text-xs shadow">
        <div className="font-medium text-foreground">
          {tr('Režim: {{mode}}', { mode })}
          {mode === 'assign_variety' && paintVariety ? ` · ${paintVariety}` : ''}
        </div>
        {cursorLatLng ? (
          <div className="font-mono text-muted-foreground">
            {cursorLatLng.lat.toFixed(6)}, {cursorLatLng.lng.toFixed(6)}
          </div>
        ) : null}
        {activeIndexLabel ? <div className="text-muted-foreground">Sloj: {activeIndexLabel}</div> : null}
      </div>

      <div className="pointer-events-auto absolute bottom-3 right-3 z-[1000] flex gap-2">
        <button
          type="button"
          className="rounded-md border border-border bg-background/95 px-2 py-1 text-xs shadow hover:bg-muted"
          onClick={() => {
            if (!fullscreenEl) return
            if (document.fullscreenElement) void document.exitFullscreen()
            else void fullscreenEl.requestFullscreen()
          }}
        >
          Pun ekran
        </button>
      </div>

      {activeIndexLabel && indexOverlayUrl ? (
        <div className="pointer-events-none absolute bottom-3 left-3 z-[1000] rounded-md bg-background/90 px-2 py-1.5 text-[10px] shadow">
          <div className="mb-1 font-medium">{activeIndexLabel}</div>
          <div
            className="h-2 w-36 rounded"
            style={{
              background: indexLegendGradient(activeIndexLabel.toLowerCase() as 'ndvi' | 'ndre' | 'ndwi'),
            }}
          />
          <div className="mt-0.5 flex justify-between text-muted-foreground">
            <span>{STRETCH[activeIndexLabel.toLowerCase() as 'ndvi' | 'ndre' | 'ndwi']?.vmin ?? ''}</span>
            <span>{STRETCH[activeIndexLabel.toLowerCase() as 'ndvi' | 'ndre' | 'ndwi']?.vmax ?? ''}</span>
          </div>
          <div className="mt-1 max-w-[14rem] text-muted-foreground">
            {tr('Sentinel-2 ~10–20 m; pojedinačna stabla se ne razlikuju pouzdano.')}
          </div>
        </div>
      ) : null}

      {children}
    </div>
  )
}
