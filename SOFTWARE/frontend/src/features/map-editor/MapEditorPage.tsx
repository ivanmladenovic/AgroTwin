import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  commitMapEditor,
  computeMapEditorMetrics,
  createMapEditorParcel,
  getMapEditorState,
  previewMapEditorLayout,
  resolveMapEditorLocation,
} from '@/features/map-editor/api'
import { refreshParcelSatellite, warmParcelEnvironment } from '@/features/orchard/api'
import { MapEditorCanvas, type MapViewSnapshot } from '@/features/map-editor/MapEditorCanvas'
import {
  DEFAULT_PLANTING_CONFIG,
  WIZARD_STEPS,
  type MapEditorMetrics,
  type MapEditorPlantingConfig,
  type MapEditorPreview,
  type MapEditorRowDraft,
  type MapEditorTreeDraft,
  type WizardStep,
} from '@/features/map-editor/types'
import {
  DEFAULT_VARIETIES,
  nextVarietyColor,
  varietyColorMap,
} from '@/features/orchard/varieties'
import type { ParcelVariety } from '@/shared/api/types'
import { ApiError } from '@/shared/lib/api'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'

import { tr } from '@/shared/i18n/i18n'
function ringToPolygon(ring: [number, number][]): GeoJSON.Polygon {
  const coords: [number, number][] = ring.map(([lat, lng]) => [lng, lat])
  const first = coords[0]
  const last = coords[coords.length - 1]
  if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
    coords.push([first[0], first[1]])
  }
  return { type: 'Polygon', coordinates: [coords] }
}

function polygonToRing(boundary: GeoJSON.Polygon | GeoJSON.MultiPolygon | null): [number, number][] {
  if (!boundary) return []
  const outer: number[][] =
    boundary.type === 'Polygon'
      ? (boundary.coordinates[0] ?? [])
      : (boundary.coordinates[0]?.[0] ?? [])
  const ring: [number, number][] = []
  for (const c of outer) {
    if (c.length < 2) continue
    ring.push([Number(c[1]), Number(c[0])])
  }
  const first = ring[0]
  const last = ring[ring.length - 1]
  if (first && last && first[0] === last[0] && first[1] === last[1]) {
    return ring.slice(0, -1)
  }
  return ring
}

function ringCentroid(ring: [number, number][]): [number, number] | null {
  if (ring.length === 0) return null
  const lat = ring.reduce((s, p) => s + p[0], 0) / ring.length
  const lng = ring.reduce((s, p) => s + p[1], 0) / ring.length
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return [lat, lng]
}

function formatHa(value: number) {
  return value.toLocaleString('sr-RS', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatM(value: number) {
  return value.toLocaleString('sr-RS', { maximumFractionDigits: 1 })
}

function edgeBearingDeg(a: [number, number], b: [number, number]) {
  const latMid = ((a[0] + b[0]) / 2) * (Math.PI / 180)
  const mLat = 111_320
  const mLon = 111_320 * Math.cos(latMid)
  const dy = (b[0] - a[0]) * mLat
  const dx = (b[1] - a[1]) * mLon
  return Math.round(((((Math.atan2(dy, dx) * 180) / Math.PI) + 360) % 180) * 10) / 10
}

function approxLengthM(a: [number, number], b: [number, number]) {
  const latMid = ((a[0] + b[0]) / 2) * (Math.PI / 180)
  const mLat = 111_320
  const mLon = 111_320 * Math.cos(latMid)
  return Math.hypot((b[0] - a[0]) * mLat, (b[1] - a[1]) * mLon)
}

/** Update one endpoint of a LineString / MultiLineString segment (GeoJSON lng/lat). */
function patchRowEndpoint(
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString,
  segmentIndex: number,
  endIndex: 0 | 1,
  lat: number,
  lng: number,
): { geometry: GeoJSON.LineString | GeoJSON.MultiLineString; start: [number, number]; end: [number, number]; length_m: number } {
  const point: [number, number] = [lng, lat]
  if (geometry.type === 'LineString') {
    const coords = geometry.coordinates.map((c) => [...c] as number[])
    if (endIndex === 0) coords[0] = point
    else coords[coords.length - 1] = point
    const start: [number, number] = [Number(coords[0]![1]), Number(coords[0]![0])]
    const end: [number, number] = [
      Number(coords[coords.length - 1]![1]),
      Number(coords[coords.length - 1]![0]),
    ]
    return {
      geometry: { type: 'LineString', coordinates: coords },
      start,
      end,
      length_m: approxLengthM(start, end),
    }
  }
  const lines = geometry.coordinates.map((line) => line.map((c) => [...c] as number[]))
  const seg = lines[segmentIndex] ?? lines[0]
  if (!seg || seg.length < 2) {
    const start: [number, number] = [lat, lng]
    return { geometry, start, end: start, length_m: 0 }
  }
  if (endIndex === 0) seg[0] = point
  else seg[seg.length - 1] = point
  lines[segmentIndex] = seg
  const start: [number, number] = [Number(seg[0]![1]), Number(seg[0]![0])]
  const end: [number, number] = [Number(seg[seg.length - 1]![1]), Number(seg[seg.length - 1]![0])]
  return {
    geometry: { type: 'MultiLineString', coordinates: lines },
    start,
    end,
    length_m: approxLengthM(start, end),
  }
}

function redistributeTreesAlongSegment(
  trees: MapEditorTreeDraft[],
  rowDraftId: string,
  start: [number, number],
  end: [number, number],
): MapEditorTreeDraft[] {
  const onRow = trees
    .filter((t) => t.row_draft_id === rowDraftId)
    .sort((a, b) => a.tree_number - b.tree_number)
  if (onRow.length === 0) return trees
  const n = onRow.length
  const startT = 0.08
  const endT = 0.08
  const span = Math.max(1e-9, 1 - startT - endT)
  const positions = onRow.map((_, i) => {
    const t = n === 1 ? 0.5 : startT + span * (i / (n - 1))
    return {
      lat: start[0] + (end[0] - start[0]) * t,
      lng: start[1] + (end[1] - start[1]) * t,
    }
  })
  const byId = new Map(onRow.map((t, i) => [t.draft_id, positions[i]!]))
  return trees.map((t) => {
    const p = byId.get(t.draft_id)
    if (!p) return t
    return { ...t, latitude: p.lat, longitude: p.lng, manually_placed: true }
  })
}

function toLocalMeters(lat: number, lng: number, originLat: number, originLng: number) {
  const mLat = 111_320
  const mLon = 111_320 * Math.cos((originLat * Math.PI) / 180)
  return {
    x: (lng - originLng) * mLon,
    y: (lat - originLat) * mLat,
  }
}

function fromLocalMeters(x: number, y: number, originLat: number, originLng: number) {
  const mLat = 111_320
  const mLon = 111_320 * Math.cos((originLat * Math.PI) / 180)
  return {
    lat: originLat + y / mLat,
    lng: originLng + x / mLon,
  }
}

/** Project a lat/lng point onto the closest point of a row geometry (along the row only). */
function projectOntoRowGeometry(
  lat: number,
  lng: number,
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString,
): { lat: number; lng: number; tAlong: number } | null {
  const lines: [number, number][][] =
    geometry.type === 'LineString'
      ? [geometry.coordinates.map((c) => [Number(c[1]), Number(c[0])] as [number, number])]
      : geometry.coordinates.map((line) =>
          line.map((c) => [Number(c[1]), Number(c[0])] as [number, number]),
        )

  let best: { lat: number; lng: number; dist2: number; tAlong: number } | null = null
  let alongOffset = 0

  for (const line of lines) {
    for (let i = 0; i < line.length - 1; i++) {
      const a = line[i]!
      const b = line[i + 1]!
      const originLat = a[0]
      const originLng = a[1]
      const A = toLocalMeters(a[0], a[1], originLat, originLng)
      const B = toLocalMeters(b[0], b[1], originLat, originLng)
      const P = toLocalMeters(lat, lng, originLat, originLng)
      const abx = B.x - A.x
      const aby = B.y - A.y
      const len2 = abx * abx + aby * aby
      if (len2 < 1e-8) continue
      let t = ((P.x - A.x) * abx + (P.y - A.y) * aby) / len2
      t = Math.max(0, Math.min(1, t))
      const qx = A.x + t * abx
      const qy = A.y + t * aby
      const dx = P.x - qx
      const dy = P.y - qy
      const dist2 = dx * dx + dy * dy
      const segLen = Math.sqrt(len2)
      const ll = fromLocalMeters(qx, qy, originLat, originLng)
      const tAlong = alongOffset + t * segLen
      if (!best || dist2 < best.dist2) {
        best = { lat: ll.lat, lng: ll.lng, dist2, tAlong }
      }
      alongOffset += segLen
    }
  }
  if (!best) return null
  return { lat: best.lat, lng: best.lng, tAlong: best.tAlong }
}

function rowSegmentsLatLng(geometry: GeoJSON.LineString | GeoJSON.MultiLineString): [number, number][][] {
  if (geometry.type === 'LineString') {
    return [geometry.coordinates.map((c) => [Number(c[1]), Number(c[0])] as [number, number])]
  }
  return geometry.coordinates.map((line) =>
    line.map((c) => [Number(c[1]), Number(c[0])] as [number, number]),
  )
}

/** Parametric position 0..1 along entire MultiLineString / LineString. */
function pointAtFractionAlongRow(
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString,
  fraction: number,
): { lat: number; lng: number } | null {
  const lines = rowSegmentsLatLng(geometry)
  const parts: Array<{ a: [number, number]; b: [number, number]; len: number }> = []
  let total = 0
  for (const line of lines) {
    for (let i = 0; i < line.length - 1; i++) {
      const a = line[i]!
      const b = line[i + 1]!
      const len = approxLengthM(a, b)
      parts.push({ a, b, len })
      total += len
    }
  }
  if (total < 1e-6 || parts.length === 0) return null
  let target = Math.max(0, Math.min(1, fraction)) * total
  for (const part of parts) {
    if (target <= part.len || part === parts[parts.length - 1]) {
      const t = part.len < 1e-9 ? 0 : target / part.len
      return {
        lat: part.a[0] + (part.b[0] - part.a[0]) * t,
        lng: part.a[1] + (part.b[1] - part.a[1]) * t,
      }
    }
    target -= part.len
  }
  return null
}

function stepIndex(step: WizardStep) {
  return WIZARD_STEPS.findIndex((s) => s.id === step)
}

export function MapEditorPage() {
  const { parcelId: routeParcelId } = useParams()
  const [searchParams] = useSearchParams()
  const isNew = !routeParcelId || routeParcelId === 'new'
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [parcelId, setParcelId] = useState<string | null>(isNew ? null : routeParcelId)
  const [step, setStep] = useState<WizardStep>(isNew ? 'basics' : 'boundary')
  const [newName, setNewName] = useState('')
  const [plantingYear, setPlantingYear] = useState(new Date().getFullYear())
  const [locationQuery, setLocationQuery] = useState('')
  const [locationLabel, setLocationLabel] = useState<string | null>(null)
  const [mapCenter, setMapCenter] = useState<[number, number] | null>(
    searchParams.get('lat') && searchParams.get('lng')
      ? [Number(searchParams.get('lat')), Number(searchParams.get('lng'))]
      : null,
  )
  const [flyTo, setFlyTo] = useState<[number, number] | null>(null)
  /** One-shot fit to existing parcel boundary after hydrate (avoids Belgrade default). */
  const [fitRingOnce, setFitRingOnce] = useState<[number, number][] | null>(null)
  const [locationBusy, setLocationBusy] = useState(false)
  const lastMapViewRef = useRef<MapViewSnapshot | null>(null)
  const [lockedView, setLockedView] = useState<MapViewSnapshot | null>(null)

  const [draftRing, setDraftRing] = useState<[number, number][]>([])
  const [ringHistory, setRingHistory] = useState<[number, number][][]>([])
  const [metrics, setMetrics] = useState<MapEditorMetrics | null>(null)
  const [selectedEdgeIndex, setSelectedEdgeIndex] = useState<number | null>(null)
  const [awaitingFirstRow, setAwaitingFirstRow] = useState(false)
  const [firstRowPicked, setFirstRowPicked] = useState(false)
  const [reviewRowNumber, setReviewRowNumber] = useState<number | null>(null)
  const [reviewAddMode, setReviewAddMode] = useState(false)
  const [targetRowCount, setTargetRowCount] = useState(20)
  const [uniformMargin, setUniformMargin] = useState(2)
  const [perEdgeMargins, setPerEdgeMargins] = useState(false)
  const [edgeMargins, setEdgeMargins] = useState<number[]>([])
  const [hoverEdgeIndex, setHoverEdgeIndex] = useState<number | null>(null)
  const [config, setConfig] = useState<MapEditorPlantingConfig>({
    ...DEFAULT_PLANTING_CONFIG,
    default_planting_year: new Date().getFullYear(),
    default_variety: null,
  })

  const [rows, setRows] = useState<MapEditorRowDraft[]>([])
  const [trees, setTrees] = useState<MapEditorTreeDraft[]>([])
  const [previewWarnings, setPreviewWarnings] = useState<string[]>([])
  const [previewBusy, setPreviewBusy] = useState(false)
  const [varieties, setVarieties] = useState<ParcelVariety[]>([])
  const [paintVariety, setPaintVariety] = useState<string | null>(null)
  const [selectedTreeId, setSelectedTreeId] = useState<string | null>(null)
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [cursor, setCursor] = useState<{ lat: number; lng: number } | null>(null)
  const [dirty, setDirty] = useState(false)
  const [hydrated, setHydrated] = useState(isNew)

  const existingQuery = useQuery({
    queryKey: ['map-editor', parcelId],
    queryFn: () => getMapEditorState(parcelId!),
    enabled: Boolean(parcelId) && !isNew,
  })

  const mode = useMemo(() => {
    // Boundary step stays in draw_boundary so user can keep adding points AND drag vertices.
    if (step === 'boundary') return 'draw_boundary'
    if (step === 'planting') {
      if (awaitingFirstRow || (rows.length > 0 && firstRowPicked)) return 'select_row'
      if (rows.length > 0 && !firstRowPicked) return 'select_row'
      return 'row_orientation'
    }
    if (step === 'review') return 'select_tree'
    if (step === 'assign') return 'assign_variety'
    return 'select'
  }, [step, selectedTreeId, awaitingFirstRow, rows.length, firstRowPicked])

  const colors = varietyColorMap(varieties)

  const treesPerRow = useMemo(() => {
    const map = new Map<number, number>()
    for (const t of trees) {
      map.set(t.row_number, (map.get(t.row_number) ?? 0) + 1)
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [trees])

  const refreshMetrics = useCallback(
    async (ring: [number, number][]) => {
      if (ring.length < 3) {
        setMetrics(null)
        return
      }
      try {
        const m = await computeMapEditorMetrics(ringToPolygon(ring), parcelId ?? undefined)
        setMetrics(m)
        setErrorMsg(null)
      } catch (err) {
        setMetrics(null)
        setErrorMsg(err instanceof ApiError ? err.message : 'Neispravna geometrija')
      }
    },
    [parcelId],
  )

  useEffect(() => {
    const state = existingQuery.data
    if (!state || hydrated) return
    setNewName(state.name)
    if (state.default_planting_year) setPlantingYear(state.default_planting_year)
    let center: [number, number] | null = null
    let hasFitRing = false
    if (state.boundary) {
      const ring = polygonToRing(state.boundary)
      setDraftRing(ring)
      setMetrics(state.metrics)
      center = ringCentroid(ring)
      if (ring.length >= 3) {
        setFitRingOnce(ring)
        hasFitRing = true
      }
    }
    if (!center && state.latitude != null && state.longitude != null) {
      center = [Number(state.latitude), Number(state.longitude)]
    }
    if (center && Number.isFinite(center[0]) && Number.isFinite(center[1])) {
      setMapCenter(center)
      // Prefer fitBounds for the full parcel; flyTo only when there is no ring.
      if (!hasFitRing) setFlyTo(center)
    }
    if (state.varieties?.length) {
      setVarieties(
        state.varieties.map((v) => ({
          name: v.name,
          role: (v.role as ParcelVariety['role']) ?? 'other',
          color: v.color ?? '#DC2626',
        })),
      )
    }
    if (state.row_spacing_m) {
      setConfig((c) => ({
        ...c,
        row_spacing_m: Number(state.row_spacing_m),
        tree_spacing_m: state.tree_spacing_m ? Number(state.tree_spacing_m) : c.tree_spacing_m,
        default_planting_year: state.default_planting_year ?? c.default_planting_year,
      }))
    }
    const geoRows: MapEditorRowDraft[] = state.rows
      .filter((r) => r.geometry)
      .map((r) => ({
        draft_id: r.id,
        row_number: r.row_number,
        segment_index: 0,
        length_m: 0,
        tree_count: r.tree_count,
        geometry: r.geometry!,
        default_variety: r.variety,
        default_planting_year: r.planting_year,
      }))
    const geoTrees: MapEditorTreeDraft[] = state.trees
      .filter((t) => t.has_geographic_position && t.latitude != null && t.longitude != null)
      .map((t) => ({
        draft_id: t.id,
        row_draft_id: t.row_id,
        row_number: t.row_number,
        tree_number: t.position_in_row,
        latitude: t.latitude!,
        longitude: t.longitude!,
        variety: t.variety,
        planting_year: t.planting_year,
        inherited_variety: false,
        manually_placed: false,
        existing_tree_id: t.id,
        existing_public_id: t.public_id,
      }))
    if (geoRows.length) setRows(geoRows)
    if (geoTrees.length) setTrees(geoTrees)
    setHydrated(true)
    setStep(state.boundary ? (geoTrees.length ? 'review' : 'planting') : 'boundary')
  }, [existingQuery.data, hydrated])

  useEffect(() => {
    setConfig((c) => ({ ...c, default_planting_year: plantingYear }))
  }, [plantingYear])

  useEffect(() => {
    if (draftRing.length < 2) return
    setEdgeMargins((prev) => {
      if (prev.length === draftRing.length) return prev
      return draftRing.map((_, i) => prev[i] ?? uniformMargin)
    })
  }, [draftRing.length, uniformMargin, draftRing])

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  const applyMarginsToConfig = useCallback(
    (base: MapEditorPlantingConfig): MapEditorPlantingConfig => {
      if (perEdgeMargins && edgeMargins.length === draftRing.length && draftRing.length >= 3) {
        const n = draftRing.length
        const ref = selectedEdgeIndex != null ? selectedEdgeIndex % n : 0
        // Quad shortcut: Stranica N maps 1:1 — ref / opposite / next / prev.
        if (n === 4) {
          const buffer = Math.min(...edgeMargins, uniformMargin)
          return {
            ...base,
            first_row_offset_m: edgeMargins[ref] ?? uniformMargin,
            last_row_offset_m: edgeMargins[(ref + 2) % 4] ?? uniformMargin,
            tree_start_offset_m: edgeMargins[(ref + 1) % 4] ?? uniformMargin,
            row_end_offset_m: edgeMargins[(ref + 3) % 4] ?? uniformMargin,
            boundary_buffer_m: Math.max(0, buffer * 0.5),
            target_row_count: targetRowCount > 0 ? targetRowCount : null,
            default_planting_year: plantingYear,
            default_variety: null,
          }
        }
        // General polygon: reference edge → first row offset; opposite parallel → last;
        // remaining near-perpendicular edges → along-row ends.
        const alongIdx: number[] = []
        const crossIdx: number[] = []
        for (let i = 0; i < n; i++) {
          const a = draftRing[i]!
          const b = draftRing[(i + 1) % n]!
          const bearing = edgeBearingDeg(a, b)
          const delta = Math.min(
            Math.abs(bearing - base.orientation_deg),
            180 - Math.abs(bearing - base.orientation_deg),
          )
          if (delta < 35) alongIdx.push(i)
          else crossIdx.push(i)
        }
        const refMid: [number, number] = [
          (draftRing[ref]![0] + draftRing[(ref + 1) % n]![0]) / 2,
          (draftRing[ref]![1] + draftRing[(ref + 1) % n]![1]) / 2,
        ]
        let opp = alongIdx.find((i) => i !== ref) ?? (ref + Math.floor(n / 2)) % n
        let best = -1
        for (const i of alongIdx) {
          if (i === ref) continue
          const mid: [number, number] = [
            (draftRing[i]![0] + draftRing[(i + 1) % n]![0]) / 2,
            (draftRing[i]![1] + draftRing[(i + 1) % n]![1]) / 2,
          ]
          const d = (mid[0] - refMid[0]) ** 2 + (mid[1] - refMid[1]) ** 2
          if (d > best) {
            best = d
            opp = i
          }
        }
        const crossOrdered = crossIdx.length
          ? crossIdx
          : Array.from({ length: n }, (_, i) => i).filter((i) => i !== ref && i !== opp)
        const buffer = Math.min(...edgeMargins, uniformMargin)
        return {
          ...base,
          first_row_offset_m: edgeMargins[ref] ?? uniformMargin,
          last_row_offset_m: edgeMargins[opp] ?? uniformMargin,
          tree_start_offset_m: edgeMargins[crossOrdered[0] ?? 0] ?? uniformMargin,
          row_end_offset_m:
            edgeMargins[crossOrdered[1] ?? crossOrdered[0] ?? 0] ?? uniformMargin,
          boundary_buffer_m: Math.max(0, buffer * 0.5),
          target_row_count: targetRowCount > 0 ? targetRowCount : null,
          default_planting_year: plantingYear,
          default_variety: null,
        }
      }
      return {
        ...base,
        first_row_offset_m: uniformMargin,
        last_row_offset_m: uniformMargin,
        tree_start_offset_m: uniformMargin,
        row_end_offset_m: uniformMargin,
        boundary_buffer_m: Math.max(0, uniformMargin * 0.35),
        target_row_count: targetRowCount > 0 ? targetRowCount : null,
        default_planting_year: plantingYear,
        default_variety: null,
      }
    },
    [
      perEdgeMargins,
      edgeMargins,
      draftRing,
      uniformMargin,
      targetRowCount,
      plantingYear,
      selectedEdgeIndex,
    ],
  )

  const resolveLocation = async () => {
    const q = locationQuery.trim()
    if (!q) {
      setErrorMsg(tr('Unesite adresu, koordinate (npr. 44.29, 21.16) ili Google Maps link.'))
      return
    }
    setLocationBusy(true)
    setErrorMsg(null)
    try {
      const result = await resolveMapEditorLocation(q)
      const center: [number, number] = [result.latitude, result.longitude]
      setMapCenter(center)
      setFlyTo(center)
      setLocationLabel(result.label)
      setDirty(true)
      setStatusMsg(
        tr('Lokacija pronađena ({{source}}). Potvrdite da biste crtali granicu.', { source: result.source }),
      )
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : tr('Lokacija nije pronađena'))
    } finally {
      setLocationBusy(false)
    }
  }

  const pushRingHistory = useCallback((ring: [number, number][]) => {
    setRingHistory((prev) => [...prev, ring.map((p) => [p[0], p[1]] as [number, number])].slice(-60))
  }, [])

  const undoBoundary = () => {
    setRingHistory((prev) => {
      if (prev.length === 0) {
        if (draftRing.length === 0) return prev
        const next = draftRing.slice(0, -1)
        setDraftRing(next)
        void refreshMetrics(next)
        setDirty(true)
        setStatusMsg(next.length ? tr('Poništeno poslednje teme.') : tr('Granica obrisana.'))
        return prev
      }
      const copy = [...prev]
      const restored = copy.pop()!
      setDraftRing(restored)
      void refreshMetrics(restored)
      setDirty(true)
      setStatusMsg(tr('Poništena poslednja izmena granice.'))
      return copy
    })
  }

  const onMapClick = (lat: number, lng: number) => {
    if (step === 'review') {
      if (reviewAddMode && reviewRowNumber != null) {
        addTreeOnReviewRow(lat, lng)
        return
      }
      return
    }
    if (step !== 'boundary') return
    pushRingHistory(draftRing)
    const next = [...draftRing, [lat, lng] as [number, number]]
    setDraftRing(next)
    setDirty(true)
    void refreshMetrics(next)
    setStatusMsg(
      next.length < 3
        ? tr('Teme {{count}} dodato — treba najmanje 3. Prevucite narandžasta temena da korigujete.', {
            count: next.length,
          })
        : tr('Teme {{count}} dodato. Prevucite temena ili dodajte nova klikom.', { count: next.length }),
    )
  }

  const onRingCommit = (ring: [number, number][]) => {
    if (ring.length < 1) return
    pushRingHistory(draftRing)
    setDraftRing(ring)
    setDirty(true)
    void refreshMetrics(ring)
    // Recompute bearing if a reference edge is still selected.
    if (selectedEdgeIndex != null && ring.length >= 2) {
      const i = selectedEdgeIndex % ring.length
      const a = ring[i]
      const b = ring[(i + 1) % ring.length]
      if (a && b) {
        const deg = edgeBearingDeg(a, b)
        setConfig((c) => ({
          ...c,
          orientation_deg: deg,
          orientation_edge_index: i,
        }))
      }
    }
    if (rows.length) {
      setRows([])
      setTrees([])
      setAwaitingFirstRow(false)
      setFirstRowPicked(false)
      setStatusMsg(tr('Granica pomerena — kliknite „Ponovo iscrtaj” da uskladite redove.'))
    } else {
      setStatusMsg(tr('Teme pomereno. Po potrebi ponovo izaberite referentnu stranicu.'))
    }
  }

  const finishPolygon = () => {
    if (draftRing.length < 3) {
      setErrorMsg('Poligon mora imati najmanje tri temena.')
      return
    }
    void refreshMetrics(draftRing)
    setStatusMsg(tr('Granica zatvorena. Prevucite temena po potrebi, zatim potvrdite.'))
  }

  const selectEdgeForOrientation = (edgeIndex: number) => {
    if (draftRing.length < 2) return
    const a = draftRing[edgeIndex]
    const b = draftRing[(edgeIndex + 1) % draftRing.length]
    if (!a || !b) return
    const deg = edgeBearingDeg(a, b)
    setSelectedEdgeIndex(edgeIndex)
    setConfig((c) => ({
      ...c,
      orientation_deg: deg,
      orientation_edge_index: edgeIndex,
    }))
    setDirty(true)
    if (rows.length) {
      setRows([])
      setTrees([])
      setAwaitingFirstRow(false)
      setFirstRowPicked(false)
      setStatusMsg(tr('Referentna stranica {{page}}. Ponovo iscrtajte redove.', { page: edgeIndex + 1 }))
    } else {
      setStatusMsg(
        tr('Referentna stranica {{page}} — redovi će ići paralelno sa njom.', { page: edgeIndex + 1 }),
      )
    }
  }

  const applyRowEndpointMove = (
    rowDraftId: string,
    segmentIndex: number,
    endIndex: 0 | 1,
    lat: number,
    lng: number,
    commit: boolean,
  ) => {
    setRows((prev) => {
      const row = prev.find((r) => r.draft_id === rowDraftId)
      if (!row) return prev
      const patched = patchRowEndpoint(row.geometry, segmentIndex, endIndex, lat, lng)
      const nextRows = prev.map((r) =>
        r.draft_id === rowDraftId
          ? { ...r, geometry: patched.geometry, length_m: Math.round(patched.length_m * 10) / 10 }
          : r,
      )
      setTrees((prevTrees) =>
        redistributeTreesAlongSegment(prevTrees, rowDraftId, patched.start, patched.end),
      )
      return nextRows
    })
    if (commit) {
      setDirty(true)
      setSelectedRowId(rowDraftId)
      setStatusMsg(tr('Red podešen — prevucite krajeve da pomerite ili blago rotirate.'))
    }
  }

  const renumberFromFirstRow = (clickedRowNumber: number) => {
    const nums = [...new Set(rows.map((r) => r.row_number))].sort((a, b) => a - b)
    const i = nums.indexOf(clickedRowNumber)
    if (i < 0) return
    // Spatially continuous: only reverse whole strip or keep — clicked end becomes row 1.
    const reverse = i >= nums.length / 2
    const ordered = reverse ? [...nums].reverse() : nums
    const remap = new Map(ordered.map((old, idx) => [old, idx + 1]))
    setRows((prev) =>
      prev.map((r) => ({
        ...r,
        row_number: remap.get(r.row_number) ?? r.row_number,
      })),
    )
    setTrees((prev) =>
      prev.map((t) => ({
        ...t,
        row_number: remap.get(t.row_number) ?? t.row_number,
      })),
    )
    setConfig((c) => ({ ...c, number_rows_ascending: !reverse }))
    setAwaitingFirstRow(false)
    setFirstRowPicked(true)
    setDirty(true)
    setStatusMsg(
      tr('Prvi red označen (bio #{{num}}). Brojanje ide od kraja koji ste izabrali.', { num: clickedRowNumber }),
    )
  }

  const runPreview = async () => {
    if (draftRing.length < 3) {
      setErrorMsg(tr('Prvo nacrtajte i potvrdite granicu.'))
      return
    }
    if (selectedEdgeIndex == null) {
      setErrorMsg(tr('Izaberite stranicu paralelno sa kojom idu redovi (klik na ivicu).'))
      return
    }
    setPreviewBusy(true)
    setErrorMsg(null)
    try {
      const nextConfig = {
        ...applyMarginsToConfig(config),
        orientation_edge_index: selectedEdgeIndex,
        orientation_deg: (() => {
          const a = draftRing[selectedEdgeIndex]
          const b = draftRing[(selectedEdgeIndex + 1) % draftRing.length]
          return a && b ? edgeBearingDeg(a, b) : config.orientation_deg
        })(),
      }
      setConfig(nextConfig)
      const result: MapEditorPreview = await previewMapEditorLayout(
        ringToPolygon(draftRing),
        nextConfig,
        parcelId ?? undefined,
      )
      setRows(result.rows.map((r) => ({ ...r, default_variety: null })))
      setTrees(
        result.trees.map((t) => ({
          ...t,
          variety: null,
          planting_year: plantingYear,
          inherited_variety: true,
        })),
      )
      setMetrics(result.metrics)
      setPreviewWarnings(result.warnings)
      const appliedSpacing = result.config.row_spacing_m
      if (appliedSpacing != null && Number.isFinite(Number(appliedSpacing))) {
        const nextSpacing = Number(appliedSpacing)
        setConfig((c) =>
          Math.abs(c.row_spacing_m - nextSpacing) > 0.001
            ? { ...c, row_spacing_m: Math.round(nextSpacing * 100) / 100 }
            : c,
        )
      }
      setDirty(true)
      setAwaitingFirstRow(true)
      setFirstRowPicked(false)
      setStatusMsg(
        tr('Iscrtano: {{count}} redova{{requested}}', {
          count: result.summary.row_count,
          requested:
            targetRowCount > 0 && result.summary.row_count !== targetRowCount
              ? tr(' (zatraženo {{count}})', { count: targetRowCount })
              : '',
        }) + tr('. Sada kliknite na mapi koji je PRVI red (kraj od kog kreće brojanje).'),
      )
    } catch (err) {
      setErrorMsg(err instanceof ApiError ? err.message : tr('Generisanje nije uspelo'))
    } finally {
      setPreviewBusy(false)
    }
  }

  const deleteTreeById = (treeId: string) => {
    const removed = trees.find((t) => t.draft_id === treeId)
    setTrees((prev) => prev.filter((t) => t.draft_id !== treeId))
    setRows((prev) =>
      prev.map((r) => {
        const count = trees.filter((t) => t.draft_id !== treeId && t.row_draft_id === r.draft_id).length
        return { ...r, tree_count: count }
      }),
    )
    if (selectedTreeId === treeId) setSelectedTreeId(null)
    setDirty(true)
    if (removed) {
      setStatusMsg(
        tr('Uklonjena sadnica R{{row}}-T{{tree}}.', {
          row: removed.row_number,
          tree: removed.tree_number,
        }),
      )
    }
  }

  const slideTreeAlongRow = (treeId: string, lat: number, lng: number, commit: boolean) => {
    const tree = trees.find((t) => t.draft_id === treeId)
    if (!tree) return
    const row =
      rows.find((r) => r.draft_id === tree.row_draft_id) ??
      rows.find((r) => r.row_number === tree.row_number)
    if (!row) return
    const projected = projectOntoRowGeometry(lat, lng, row.geometry)
    if (!projected) return
    setTrees((prev) =>
      prev.map((t) =>
        t.draft_id === treeId
          ? {
              ...t,
              latitude: projected.lat,
              longitude: projected.lng,
              manually_placed: true,
            }
          : t,
      ),
    )
    setSelectedTreeId(treeId)
    setReviewRowNumber(tree.row_number)
    if (commit) {
      setDirty(true)
      setStatusMsg(
        tr('Sadnica R{{row}}-T{{tree}} pomerena duž reda.', {
          row: tree.row_number,
          tree: tree.tree_number,
        }),
      )
    }
  }

  const addTreeOnReviewRow = (lat?: number, lng?: number) => {
    if (reviewRowNumber == null) {
      setErrorMsg(tr('Prvo izaberite red u tabeli (ili kliknite sadnicu tog reda).'))
      return
    }
    const row =
      rows.find((r) => r.row_number === reviewRowNumber && r.segment_index === 0) ??
      rows.find((r) => r.row_number === reviewRowNumber)
    if (!row) {
      setErrorMsg(tr('Nema geometrije za izabrani red.'))
      return
    }
    let pos: { lat: number; lng: number } | null = null
    if (lat != null && lng != null) {
      pos = projectOntoRowGeometry(lat, lng, row.geometry)
    }
    if (!pos) {
      // Place in the largest gap along the row (by existing trees), else at mid.
      const onRow = trees
        .filter((t) => t.row_number === reviewRowNumber)
        .map((t) => projectOntoRowGeometry(t.latitude, t.longitude, row.geometry))
        .filter((p): p is NonNullable<typeof p> => Boolean(p))
        .sort((a, b) => a.tAlong - b.tAlong)
      if (onRow.length === 0) {
        pos = pointAtFractionAlongRow(row.geometry, 0.5)
      } else if (onRow.length === 1) {
        pos = pointAtFractionAlongRow(row.geometry, 0.75)
      } else {
        let bestI = 0
        let bestGap = -1
        for (let i = 0; i < onRow.length - 1; i++) {
          const gap = onRow[i + 1]!.tAlong - onRow[i]!.tAlong
          if (gap > bestGap) {
            bestGap = gap
            bestI = i
          }
        }
        const midT = (onRow[bestI]!.tAlong + onRow[bestI + 1]!.tAlong) / 2
        // Convert midT meters-along to fraction approximately via pointAtFraction using total length
        const total =
          rowSegmentsLatLng(row.geometry).reduce((acc, line) => {
            for (let i = 0; i < line.length - 1; i++) {
              acc += approxLengthM(line[i]!, line[i + 1]!)
            }
            return acc
          }, 0) || 1
        pos = pointAtFractionAlongRow(row.geometry, midT / total)
      }
    }
    if (!pos) return
    const nextNum =
      Math.max(0, ...trees.filter((t) => t.row_number === reviewRowNumber).map((t) => t.tree_number)) + 1
    const draftId = `manual-t-r${reviewRowNumber}-${Date.now()}`
    setTrees((prev) => [
      ...prev,
      {
        draft_id: draftId,
        row_draft_id: row.draft_id,
        row_number: reviewRowNumber,
        tree_number: nextNum,
        latitude: pos!.lat,
        longitude: pos!.lng,
        variety: row.default_variety,
        planting_year: row.default_planting_year ?? plantingYear,
        inherited_variety: true,
        manually_placed: true,
      },
    ])
    setRows((prev) =>
      prev.map((r) =>
        r.row_number === reviewRowNumber ? { ...r, tree_count: r.tree_count + 1 } : r,
      ),
    )
    setSelectedTreeId(draftId)
    setReviewAddMode(false)
    setDirty(true)
    setStatusMsg(
      tr('Dodata sadnica u red {{row}}. Prevucite je duž linije reda po potrebi.', { row: reviewRowNumber }),
    )
  }

  const paintRowWithVariety = (rowDraftId: string, varietyName: string) => {
    const row = rows.find((r) => r.draft_id === rowDraftId)
    if (!row) return
    setRows((prev) =>
      prev.map((r) => (r.row_number === row.row_number ? { ...r, default_variety: varietyName } : r)),
    )
    setTrees((prev) =>
      prev.map((t) =>
        t.row_number === row.row_number
          ? { ...t, variety: varietyName, inherited_variety: true }
          : t,
      ),
    )
    setDirty(true)
    setStatusMsg(tr('Red {{row}} → {{variety}}', { row: row.row_number, variety: varietyName }))
  }

  const setRowYear = (rowNumber: number, year: number | null) => {
    setRows((prev) =>
      prev.map((r) => (r.row_number === rowNumber ? { ...r, default_planting_year: year } : r)),
    )
    setTrees((prev) =>
      prev.map((t) =>
        t.row_number === rowNumber
          ? { ...t, planting_year: year ?? plantingYear }
          : t,
      ),
    )
    setDirty(true)
  }

  const commitMutation = useMutation({
    mutationFn: async () => {
      if (draftRing.length < 3) throw new Error(tr('Nedostaje granica'))
      const boundary = ringToPolygon(draftRing)
      const finalConfig = {
        ...applyMarginsToConfig(config),
        default_variety: varieties[0]?.name ?? null,
        default_planting_year: plantingYear,
      }
      const varietyPayload = varieties.map((v) => ({
        name: v.name,
        role: v.role,
        color: v.color,
      }))
      let id = parcelId
      if (!id) {
        const created = await createMapEditorParcel({
          name: newName.trim() || tr('Nova parcela'),
          boundary,
          config: finalConfig,
          commit_planting: false,
        })
        id = created.parcel_id
      }
      const commit = await commitMapEditor(id, {
        boundary,
        config: finalConfig,
        replace_planting: true,
        create_missing_trees: true,
        remove_unmatched_trees: false,
        update_area_from_geometry: true,
        rows,
        trees,
        varieties: varietyPayload,
      })
      return { parcelId: id, commit }
    },
    onSuccess: (data) => {
      setDirty(false)
      setParcelId(data.parcelId)
      void queryClient.invalidateQueries({ queryKey: ['map-editor'] })
      void queryClient.invalidateQueries({ queryKey: ['orchard-twin'] })
      void queryClient.invalidateQueries({ queryKey: ['parcels'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      // Warm weather, SoilGrids, and satellite indices now that lat/lng + boundary exist.
      void warmParcelEnvironment(data.parcelId)
        .then(() => {
          void queryClient.invalidateQueries({ queryKey: ['parcel-weather', data.parcelId] })
          void queryClient.invalidateQueries({ queryKey: ['parcel-soil', data.parcelId] })
        })
        .catch(() => undefined)
      void refreshParcelSatellite(data.parcelId)
        .then(() => {
          void queryClient.invalidateQueries({ queryKey: ['parcel-satellite', data.parcelId] })
        })
        .catch(() => undefined)
      setStatusMsg(tr('Parcela sačuvana. Prognoza, zemljište i satelitski indeksi se ažuriraju u pozadini.'))
      navigate(`/orchard/${data.parcelId}`, { replace: true })
    },
    onError: (err) => {
      setErrorMsg(err instanceof ApiError ? err.message : err instanceof Error ? err.message : tr('Čuvanje nije uspelo'))
    },
  })

  const canGoNext = (): boolean => {
    if (step === 'basics') {
      return newName.trim().length >= 1 && plantingYear >= 1900 && Boolean(mapCenter)
    }
    if (step === 'boundary') return draftRing.length >= 3 && Boolean(metrics) && !metrics?.self_intersecting
    if (step === 'planting') {
      return selectedEdgeIndex != null && rows.length > 0 && firstRowPicked
    }
    if (step === 'review') return trees.length > 0
    if (step === 'varieties') return varieties.length >= 1
    if (step === 'assign') return rows.every((r) => r.default_variety)
    return true
  }

  const goNext = async () => {
    setErrorMsg(null)
    if (step === 'basics') {
      if (!newName.trim()) {
        setErrorMsg(tr('Unesite naziv zasada.'))
        return
      }
      if (!mapCenter) {
        setErrorMsg(tr('Prvo pronađite lokaciju — kliknite „Pronađi na mapi”.'))
        return
      }
      // Capture the exact view the user framed BEFORE step change / layout reflow.
      const snapshot = lastMapViewRef.current
      if (snapshot) setLockedView(snapshot)
      setFlyTo(null)
      setStep('boundary')
      setStatusMsg(null)
      return
    }
    if (step === 'boundary') {
      if (!canGoNext()) {
        setErrorMsg(tr('Zatvorite validan poligon (najmanje 3 temena) pre nastavka.'))
        return
      }
      setStep('planting')
      setStatusMsg(tr('Unesite razmake i izaberite stranicu paralelno sa kojom idu redovi.'))
      return
    }
    if (step === 'planting') {
      if (selectedEdgeIndex == null) {
        setErrorMsg(tr('Izaberite referentnu stranicu na mapi (klik na ivicu).'))
        return
      }
      if (rows.length === 0) {
        await runPreview()
        return
      }
      if (!firstRowPicked) {
        setErrorMsg(tr('Kliknite na mapi koji je prvi red (kraj od kog kreće brojanje).'))
        return
      }
      setStep('review')
      setReviewRowNumber(null)
      setReviewAddMode(false)
      setSelectedTreeId(null)
      setStatusMsg(
        tr('Izaberite red, zatim: prevucite sadnicu duž linije reda, dodajte ili obrišite (dvoklik / dugme).'),
      )
      return
    }
    if (step === 'review') {
      setStep('varieties')
      setStatusMsg(tr('Dodajte sorte zasada i boju za svaku.'))
      return
    }
    if (step === 'varieties') {
      if (varieties.length === 0) {
        setErrorMsg(tr('Dodajte bar jednu sortu.'))
        return
      }
      setStep('assign')
      setPaintVariety(varieties[0]?.name ?? null)
      setStatusMsg(tr('Kliknite sortu, zatim redove na mapi. Po potrebi promenite godinu reda.'))
      return
    }
    if (step === 'assign') {
      const missing = rows.filter((r) => !r.default_variety)
      if (missing.length) {
        setErrorMsg(
          tr('Nedostaje sorta za redove: {{rows}}', {
            rows: [...new Set(missing.map((r) => r.row_number))].join(', '),
          }),
        )
        return
      }
      setStep('save')
      return
    }
    if (step === 'save') {
      commitMutation.mutate()
    }
  }

  const goBack = () => {
    setErrorMsg(null)
    const idx = stepIndex(step)
    if (idx <= 0) return
    const prev = WIZARD_STEPS[idx - 1]
    if (!prev) return
    if (prev.id === 'basics') setLockedView(null)
    setStep(prev.id)
  }

  const addVariety = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    if (varieties.some((v) => v.name.toLowerCase() === trimmed.toLowerCase())) {
      setErrorMsg(tr('Ta sorta je već dodata.'))
      return
    }
    const color = nextVarietyColor(varieties)
    setVarieties((prev) => [
      ...prev,
      { name: trimmed, role: prev.length === 0 ? 'main' : 'pollinator', color },
    ])
    setDirty(true)
  }

  const effectiveMapCenter = mapCenter ?? ([44.8176, 20.4633] as [number, number])

  return (
    <div className="flex h-[calc(100vh-5.5rem)] min-h-[560px] w-full flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link to={parcelId ? `/orchard/${parcelId}` : '/orchard'} className="hover:underline">
              {tr('← Voćnjak')}
            </Link>
            <span>{tr('· Nova parcela (mapa)')}</span>
          </div>
          <h1 className="text-xl font-semibold">{newName.trim() || tr('Nova parcela')}</h1>
          <p className="text-sm text-muted-foreground">
            {tr('Vođeni unos na satelitskoj mapi — granica, redovi, sorte.')}
          </p>
        </div>
      </div>

      <ol className="flex flex-wrap gap-1">
        {WIZARD_STEPS.map((s, i) => {
          const active = s.id === step
          const done = stepIndex(step) > i
          return (
            <li key={s.id}>
              <button
                type="button"
                disabled={i > stepIndex(step) && !done}
                onClick={() => {
                  if (i <= stepIndex(step)) setStep(s.id)
                }}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-xs',
                  active && 'border-primary bg-primary text-primary-foreground',
                  done && !active && 'border-emerald-600/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100',
                  !active && !done && 'border-border bg-background text-muted-foreground',
                )}
              >
                {i + 1}. {tr(s.label)}
              </button>
            </li>
          )
        })}
      </ol>

      {/* Fixed-height strip so banners don't resize the map when step changes. */}
      <div className="flex min-h-[2.75rem] flex-col justify-center gap-1 text-sm">
        {errorMsg ? (
          <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-danger">{errorMsg}</div>
        ) : null}
        {statusMsg && !errorMsg ? (
          <div className="rounded-md border border-border bg-muted/40 px-3 py-2">{statusMsg}</div>
        ) : null}
        {previewWarnings.map((w) => (
          <div
            key={w}
            className="rounded-md border border-amber-700/50 bg-amber-100 px-3 py-1.5 font-medium text-amber-950 dark:border-amber-400/40 dark:bg-amber-950 dark:text-amber-50"
          >
            {w}
          </div>
        ))}
      </div>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-h-0 min-w-0 flex-col">
          <MapEditorCanvas
            className="min-h-0 flex-1"
            mode={mode}
            basemap="esri"
            draftRing={draftRing}
            committedBoundary={null}
            hideCommittedBoundary
            mapCenter={effectiveMapCenter}
            flyTo={flyTo}
            flyToZoom={17}
            initialZoom={mapCenter ? 17 : 13}
            fitRingOnce={fitRingOnce}
            onFitRingDone={() => setFitRingOnce(null)}
            lockedView={step === 'boundary' || step === 'review' ? lockedView : null}
            onViewChange={(view) => {
              lastMapViewRef.current = view
            }}
            rows={step === 'basics' || step === 'boundary' ? [] : rows}
            trees={
              step === 'review' || step === 'varieties' || step === 'assign' || step === 'save'
                ? trees
                : step === 'planting' && rows.length
                  ? trees
                  : []
            }
            varietyColors={colors}
            varietyFilter={null}
            paintVariety={paintVariety}
            showBoundary={step !== 'review'}
            showRows={step !== 'boundary' && step !== 'basics' && step !== 'review'}
            showTrees={
              step === 'review' ||
              step === 'assign' ||
              step === 'save' ||
              step === 'varieties' ||
              (step === 'planting' && rows.length > 0)
            }
            allowVertexEdit={step === 'planting' || step === 'boundary'}
            showOrientationEdges={step === 'planting'}
            allowRowEndpointEdit={step === 'planting' && rows.length > 0}
            onRowEndpointLive={(rowDraftId, segmentIndex, endIndex, lat, lng) => {
              applyRowEndpointMove(rowDraftId, segmentIndex, endIndex, lat, lng, false)
            }}
            onRowEndpointCommit={(rowDraftId, segmentIndex, endIndex, lat, lng) => {
              applyRowEndpointMove(rowDraftId, segmentIndex, endIndex, lat, lng, true)
            }}
            allowTreeSlideAlongRow={step === 'review'}
            allowSelectTreeMapClick={step === 'review' && reviewAddMode}
            onTreeSlide={(treeId, lat, lng, commit) => {
              if (step === 'review') slideTreeAlongRow(treeId, lat, lng, commit)
            }}
            onTreeDelete={(treeId) => {
              if (step === 'review') deleteTreeById(treeId)
            }}
            highlightRowNumber={step === 'review' ? reviewRowNumber : null}
            indexOverlayUrl={null}
            indexBounds={null}
            indexOpacity={0.65}
            activeIndexLabel={null}
            orientationPreview={null}
            selectedEdgeIndex={selectedEdgeIndex}
            highlightEdgeIndex={hoverEdgeIndex}
            measurePoints={[]}
            cursorLatLng={cursor}
            onCursorMove={setCursor}
            onMapClick={onMapClick}
            onRingCommit={onRingCommit}
            onSelectEdge={(idx) => {
              // Allow changing reference side anytime on planting (also after redraw clear).
              if (step === 'planting') {
                selectEdgeForOrientation(idx)
              }
            }}
            onTreeSelect={(id) => {
              if (step === 'review') {
                const tree = trees.find((t) => t.draft_id === id)
                setSelectedTreeId(id)
                if (tree) setReviewRowNumber(tree.row_number)
                setReviewAddMode(false)
                return
              }
              setSelectedTreeId(id)
            }}
            onRowSelect={(id) => {
              setSelectedRowId(id)
              if (step === 'planting' && (awaitingFirstRow || !firstRowPicked) && rows.length > 0) {
                const row = rows.find((r) => r.draft_id === id)
                if (row) renumberFromFirstRow(row.row_number)
                return
              }
              if (step === 'assign' && paintVariety) {
                paintRowWithVariety(id, paintVariety)
              }
            }}
            selectedTreeId={selectedTreeId}
            selectedRowId={selectedRowId}
          />
          {metrics && (step === 'boundary' || step === 'planting' || step === 'review') ? (
            <div className="text-xs text-muted-foreground">
              {tr('Površina:')}{' '}
              <strong className="text-foreground">{formatHa(metrics.area_ha)} ha</strong>
              {' · '}
              Obim: {formatM(metrics.perimeter_m)} m
              {cursor ? ` · kurzor ${cursor.lat.toFixed(5)}, ${cursor.lng.toFixed(5)}` : null}
            </div>
          ) : null}
        </div>

        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-lg border border-border bg-card p-3 text-sm">
          {step === 'basics' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('1. Naziv, godina i lokacija')}</h2>
              <label className="flex flex-col gap-1 text-xs">
                Naziv zasada
                <input
                  className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value)
                    setDirty(true)
                  }}
                  placeholder="npr. Kusiljevo Sever"
                  autoFocus
                />
              </label>
              <label className="flex flex-col gap-1 text-xs">
                Godina sadnje (podrazumevana za redove)
                <input
                  type="number"
                  min={1900}
                  max={2100}
                  className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                  value={plantingYear}
                  onChange={(e) => {
                    setPlantingYear(Number(e.target.value))
                    setDirty(true)
                  }}
                />
              </label>
              <div className="border-t border-border pt-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  Unesite adresu, koordinate (44.8176, 20.4633) ili Google Maps link — mapa se centrira.
                </p>
                <textarea
                  className="min-h-[72px] w-full rounded border border-border bg-background px-2 py-1.5 text-sm"
                  value={locationQuery}
                  onChange={(e) => setLocationQuery(e.target.value)}
                  placeholder="Adresa / koordinate / maps.app.goo.gl/…"
                />
                <Button
                  type="button"
                  className="mt-2 w-full"
                  onClick={() => void resolveLocation()}
                  disabled={locationBusy}
                >
                  {locationBusy ? tr('Tražim…') : tr('Pronađi na mapi')}
                </Button>
                {locationLabel && mapCenter ? (
                  <div className="mt-2 rounded border border-border bg-muted/30 px-2 py-2 text-xs">
                    <div className="font-medium">{locationLabel}</div>
                    <div className="text-muted-foreground">
                      {mapCenter[0].toFixed(6)}, {mapCenter[1].toFixed(6)}
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          {step === 'boundary' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('2. Granice parcele')}</h2>
              <p className="text-xs text-muted-foreground">
                {tr('Prikaz sa prethodnog koraka je sačuvan i zaključan (bez pomeranja/zuma). Klikom dodajte')}
                {tr('temena; narandžasta temena prevucite. Undo briše poslednju izmenu.')}
              </p>
              {draftRing.length > 0 && draftRing.length < 3 ? (
                <p className="rounded-md border border-amber-700/40 bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-950 dark:border-amber-400/40 dark:bg-amber-950 dark:text-amber-50">
                  {tr('Dodajte još temena ({{count}}/3+).', { count: draftRing.length })}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={undoBoundary}
                  disabled={draftRing.length === 0 && ringHistory.length === 0}
                >
                  Undo
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={draftRing.length === 0}
                  onClick={() => {
                    pushRingHistory(draftRing)
                    setDraftRing([])
                    setRingHistory([])
                    setMetrics(null)
                    setRows([])
                    setTrees([])
                  }}
                >
                  {tr('Obriši sve')}
                </Button>
              </div>
              <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                <dt className="text-muted-foreground">Temena</dt>
                <dd>{draftRing.length}</dd>
                <dt className="text-muted-foreground">{tr('Površina')}</dt>
                <dd className="font-medium">{metrics ? `${formatHa(metrics.area_ha)} ha` : '—'}</dd>
                <dt className="text-muted-foreground">Obim</dt>
                <dd>{metrics ? `${formatM(metrics.perimeter_m)} m` : '—'}</dd>
              </dl>
            </section>
          ) : null}

          {step === 'planting' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('3. Raspored sadnje')}</h2>
              {awaitingFirstRow || (rows.length > 0 && !firstRowPicked) ? (
                <p className="rounded-md border border-amber-700/40 bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-950 dark:border-amber-400/40 dark:bg-amber-950 dark:text-amber-50">
                  {tr(
                    'Kliknite liniju reda koji je prvi. Plave tačke na krajevima reda prevucite da pomerite / blago rotirate taj red.',
                  )}
                </p>
              ) : (
                <p className="text-xs text-foreground/80">
                  {tr(
                    'Prevucite plave tačke na krajevima reda da pomerite ili rotirate pojedinačan red. Narandžasta temena = granica. Klik na ivicu = referentna stranica.',
                  )}
                </p>
              )}
              {selectedEdgeIndex != null ? (
                <p className="text-xs text-foreground">
                  Referentna stranica: <strong>{selectedEdgeIndex + 1}</strong>
                  {firstRowPicked ? tr(' · prvi red označen') : null}
                </p>
              ) : (
                <p className="rounded-md border border-amber-700/40 bg-amber-100 px-2 py-1.5 text-xs font-medium text-amber-950 dark:border-amber-400/40 dark:bg-amber-950 dark:text-amber-50">
                  {tr('Još nije izabrana stranica.')}
                </p>
              )}
              <label className="flex flex-col gap-0.5 text-xs">
                Broj redova
                <input
                  type="number"
                  min={1}
                  className="rounded border border-border bg-background px-2 py-1"
                  value={targetRowCount}
                  onChange={(e) => setTargetRowCount(Number(e.target.value))}
                />
              </label>
              <label className="flex flex-col gap-0.5 text-xs">
                {tr('Razmak između redova (m)')}
                <input
                  type="number"
                  min={0.5}
                  step={0.1}
                  className="rounded border border-border bg-background px-2 py-1"
                  value={config.row_spacing_m}
                  onChange={(e) => setConfig((c) => ({ ...c, row_spacing_m: Number(e.target.value) }))}
                />
              </label>
              <label className="flex flex-col gap-0.5 text-xs">
                {tr('Razmak između sadnica (m)')}
                <input
                  type="number"
                  min={0.5}
                  step={0.1}
                  className="rounded border border-border bg-background px-2 py-1"
                  value={config.tree_spacing_m}
                  onChange={(e) => setConfig((c) => ({ ...c, tree_spacing_m: Number(e.target.value) }))}
                />
              </label>
              <label className="flex flex-col gap-0.5 text-xs">
                Razmak od svih granica (m)
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  className="rounded border border-border bg-background px-2 py-1"
                  value={uniformMargin}
                  onChange={(e) => setUniformMargin(Number(e.target.value))}
                  disabled={perEdgeMargins}
                />
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={perEdgeMargins}
                  onChange={(e) => setPerEdgeMargins(e.target.checked)}
                />
                {tr('Različita rastojanja od svake granice')}
              </label>
              {perEdgeMargins ? (
                <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
                  <li className="pb-1 text-[10px] text-muted-foreground">
                    Brojevi se poklapaju sa oznakama na mapi (Stranica 1…{draftRing.length}).
                  </li>
                  {draftRing.map((_, i) => (
                    <li
                      key={i}
                      className={cn(
                        'flex items-center gap-2 rounded px-1 py-0.5',
                        selectedEdgeIndex === i && 'bg-cyan-500/10',
                        hoverEdgeIndex === i && 'bg-amber-500/10',
                      )}
                      onMouseEnter={() => setHoverEdgeIndex(i)}
                      onMouseLeave={() => setHoverEdgeIndex(null)}
                    >
                      <span className="w-[4.75rem] shrink-0 font-medium text-foreground">
                        Stranica {i + 1}
                        {selectedEdgeIndex === i ? ' ★' : ''}
                      </span>
                      <input
                        type="number"
                        min={0}
                        step={0.1}
                        className="w-full rounded border border-border bg-background px-2 py-1"
                        value={edgeMargins[i] ?? uniformMargin}
                        onChange={(e) => {
                          const v = Number(e.target.value)
                          setEdgeMargins((prev) => {
                            const next = [...prev]
                            next[i] = v
                            return next
                          })
                        }}
                      />
                      <span className="text-muted-foreground">m</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {rows.length > 0 && firstRowPicked ? (
                <div className="rounded border border-border bg-muted/30 px-2 py-1.5 text-xs">
                  Redova: {treesPerRow.length} · Sadnica: {trees.length}
                </div>
              ) : null}
              <Button
                type="button"
                onClick={() => void runPreview()}
                disabled={previewBusy || selectedEdgeIndex == null || awaitingFirstRow}
              >
                {previewBusy ? 'Iscrtavam…' : rows.length ? tr('Ponovo iscrtaj') : tr('Iscrtaj redove i sadnice')}
              </Button>
              {rows.length > 0 && firstRowPicked ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setAwaitingFirstRow(true)
                    setFirstRowPicked(false)
                    setStatusMsg(tr('Kliknite prvi red na mapi.'))
                  }}
                >
                  Promeni prvi red
                </Button>
              ) : null}
            </section>
          ) : null}

          {step === 'review' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('4. Pregled sadnica')}</h2>
              <p className="text-xs text-muted-foreground">
                Izaberite red. Prevucite sadnicu <strong>{tr('samo duž linije reda')}</strong> (ne levo/desno).
                {tr('Dodajte klikom na mapu (u režimu dodavanja) ili obrišite dvoklikom / dugmetom.')}
              </p>
              <div className="max-h-56 overflow-y-auto rounded border border-border">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-muted/80">
                    <tr>
                      <th className="px-2 py-1 text-left font-medium">Red</th>
                      <th className="px-2 py-1 text-right font-medium">{tr('Sadnica')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {treesPerRow.map(([rowNum, count]) => (
                      <tr
                        key={rowNum}
                        className={cn(
                          'cursor-pointer border-t border-border hover:bg-muted/50',
                          reviewRowNumber === rowNum && 'bg-primary/10',
                        )}
                        onClick={() => {
                          setReviewRowNumber(rowNum)
                          setSelectedTreeId(null)
                          setReviewAddMode(false)
                          setStatusMsg(
                            tr('Aktivan red {{row}}. Prevucite sadnice duž reda ili dodajte/obrišite.', {
                              row: rowNum,
                            }),
                          )
                        }}
                      >
                        <td className="px-2 py-1 font-medium">Red {rowNum}</td>
                        <td className="px-2 py-1 text-right">{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs">
                Ukupno: <strong>{trees.length}</strong> sadnica
                {reviewRowNumber != null ? (
                  <>
                    {' '}
                    · aktivan <strong>red {reviewRowNumber}</strong>
                  </>
                ) : null}
              </p>
              <div className="flex flex-col gap-1.5">
                <Button
                  type="button"
                  size="sm"
                  variant={reviewAddMode ? 'default' : 'outline'}
                  disabled={reviewRowNumber == null}
                  onClick={() => {
                    if (reviewRowNumber == null) return
                    setReviewAddMode((v) => !v)
                    setStatusMsg(
                      reviewAddMode
                        ? tr('Red {{row}} aktivan.', { row: reviewRowNumber })
                        : tr(
                            tr('Dodavanje u red {{row}}: kliknite na mapi duž reda, ili dugme „Dodaj ovde”.'),
                            { row: reviewRowNumber },
                          ),
                    )
                  }}
                >
                  {reviewAddMode ? tr('Otkaži dodavanje') : tr('Dodaj sadnicu u red')}
                </Button>
                {reviewAddMode ? (
                  <Button type="button" size="sm" variant="outline" onClick={() => addTreeOnReviewRow()}>
                    {tr('Dodaj u najveći razmak')}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!selectedTreeId}
                  onClick={() => {
                    if (selectedTreeId) deleteTreeById(selectedTreeId)
                  }}
                >
                  {tr('Obriši izabranu sadnicu')}
                </Button>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={() => setStep('planting')}>
                Nazad — ispravi raspored
              </Button>
            </section>
          ) : null}

          {step === 'varieties' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('5. Sorte na zasadu')}</h2>
              <p className="text-xs text-muted-foreground">{tr('Izaberite iz liste ili unesite novu, pa boju.')}</p>
              <label className="flex flex-col gap-1 text-xs">
                Brzi izbor
                <select
                  className="rounded border border-border bg-background px-2 py-1.5"
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value) {
                      addVariety(e.target.value)
                      e.target.value = ''
                    }
                  }}
                >
                  <option value="">{tr('— najčešće sorte —')}</option>
                  {DEFAULT_VARIETIES.map((v) => (
                    <option key={v.name} value={v.name}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </label>
              <form
                className="flex gap-2"
                onSubmit={(e) => {
                  e.preventDefault()
                  const fd = new FormData(e.currentTarget)
                  addVariety(String(fd.get('custom') ?? ''))
                  e.currentTarget.reset()
                }}
              >
                <input
                  name="custom"
                  className="flex-1 rounded border border-border bg-background px-2 py-1 text-xs"
                  placeholder="Nova sorta…"
                />
                <Button type="submit" size="sm" variant="outline">
                  Dodaj
                </Button>
              </form>
              <ul className="space-y-2">
                {varieties.map((v, idx) => (
                  <li key={v.name} className="flex items-center gap-2 text-xs">
                    <input
                      type="color"
                      value={v.color}
                      onChange={(e) => {
                        const color = e.target.value
                        setVarieties((prev) => prev.map((x, i) => (i === idx ? { ...x, color } : x)))
                      }}
                      className="h-8 w-10 cursor-pointer rounded border border-border bg-transparent p-0"
                    />
                    <span className="flex-1 font-medium">{v.name}</span>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-danger"
                      onClick={() => setVarieties((prev) => prev.filter((_, i) => i !== idx))}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {step === 'assign' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('6. Dodela sorte redu')}</h2>
              <p className="text-xs text-muted-foreground">
                Kliknite sortu, zatim red na mapi. Godina sadnje podrazumevano {plantingYear}.
              </p>
              <ul className="space-y-1.5">
                {varieties.map((v) => (
                  <li key={v.name}>
                    <button
                      type="button"
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md border px-2 py-1.5 text-left text-xs',
                        paintVariety === v.name ? 'border-primary bg-primary/10' : 'border-border hover:bg-muted',
                      )}
                      onClick={() => setPaintVariety(v.name)}
                    >
                      <span className="inline-block h-3.5 w-3.5 rounded-full" style={{ background: v.color }} />
                      <span className="flex-1 font-medium">{v.name}</span>
                      <span className="text-muted-foreground">
                        {rows.filter((r) => r.default_variety === v.name).length} red.
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="max-h-48 space-y-1 overflow-y-auto rounded border border-border p-2 text-xs">
                {[...new Map(rows.map((r) => [r.row_number, r])).values()].map((r) => (
                  <div key={r.row_number} className="flex items-center gap-2 border-b border-border/60 py-1 last:border-0">
                    <span className="w-12 shrink-0">Red {r.row_number}</span>
                    <span className="flex-1 truncate text-muted-foreground">{r.default_variety ?? '—'}</span>
                    <input
                      type="number"
                      min={1900}
                      max={2100}
                      className="w-16 rounded border border-border bg-background px-1 py-0.5"
                      title={tr('Godina sadnje reda')}
                      value={r.default_planting_year ?? plantingYear}
                      onChange={(e) => setRowYear(r.row_number, Number(e.target.value))}
                    />
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {step === 'save' ? (
            <section className="space-y-3">
              <h2 className="font-semibold">{tr('7. Potvrda i čuvanje')}</h2>
              <ul className="space-y-1 text-xs text-muted-foreground">
                <li>
                  {tr('Naziv:')}{' '}
                  <strong className="text-foreground">{newName}</strong>
                </li>
                <li>
                  {tr('Godina:')}{' '}
                  <strong className="text-foreground">{plantingYear}</strong>
                </li>
                <li>
                  {tr('Površina:')}{' '}
                  <strong className="text-foreground">{metrics ? `${formatHa(metrics.area_ha)} ha` : '—'}</strong>
                </li>
                <li>
                  {tr('Redova / sadnica:')}{' '}
                  <strong className="text-foreground">
                    {treesPerRow.length} / {trees.length}
                  </strong>
                </li>
                <li>
                  Sorte: <strong className="text-foreground">{varieties.map((v) => v.name).join(', ')}</strong>
                </li>
              </ul>
              <Button type="button" onClick={() => commitMutation.mutate()} disabled={commitMutation.isPending}>
                {commitMutation.isPending ? tr('Čuvam…') : tr('Sačuvaj parcelu')}
              </Button>
            </section>
          ) : null}

          <div className="mt-auto flex gap-2 border-t border-border pt-3">
            <Button type="button" variant="outline" className="flex-1" onClick={goBack} disabled={step === 'basics'}>
              Nazad
            </Button>
            {step !== 'save' ? (
              <Button
                type="button"
                className="flex-1"
                onClick={() => void goNext()}
                disabled={previewBusy || commitMutation.isPending}
              >
                {step === 'planting' && rows.length === 0
                  ? tr('Iscrtaj redove')
                  : step === 'planting' && !firstRowPicked
                    ? tr('Označite prvi red')
                    : 'Dalje'}
              </Button>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  )
}
