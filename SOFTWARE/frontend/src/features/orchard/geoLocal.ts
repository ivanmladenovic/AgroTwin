import type { OrchardTwin, TreeMapItem } from '@/shared/api/types'

export type LocalPoint = { x: number; y: number }

/** Same local-meters frame as backend map-editor commit (NW origin, y grows south). */
export function projectLatLng(
  lat: number,
  lng: number,
  originLat: number,
  originLng: number,
): LocalPoint {
  const mLat = 111_320
  const mLon = 111_320 * Math.cos((originLat * Math.PI) / 180)
  return {
    x: (lng - originLng) * mLon,
    y: (originLat - lat) * mLat,
  }
}

export function geoOriginFromTrees(trees: TreeMapItem[]): { lat: number; lng: number } | null {
  const geo = trees.filter(
    (t) => t.status !== 'removed' && t.latitude != null && t.longitude != null,
  )
  if (geo.length === 0) return null
  return {
    lat: Math.max(...geo.map((t) => Number(t.latitude))),
    lng: Math.min(...geo.map((t) => Number(t.longitude))),
  }
}

export function ringLatLngFromBoundary(
  boundary: Record<string, unknown> | null | undefined,
): [number, number][] {
  if (!boundary || typeof boundary !== 'object') return []
  const type = boundary.type
  const coords = boundary.coordinates as unknown
  if (type === 'Polygon' && Array.isArray(coords) && Array.isArray(coords[0])) {
    return (coords[0] as number[][])
      .filter((c) => c.length >= 2)
      .map((c) => [Number(c[1]), Number(c[0])] as [number, number])
  }
  if (
    type === 'MultiPolygon' &&
    Array.isArray(coords) &&
    Array.isArray(coords[0]) &&
    Array.isArray(coords[0][0])
  ) {
    return (coords[0][0] as number[][])
      .filter((c) => c.length >= 2)
      .map((c) => [Number(c[1]), Number(c[0])] as [number, number])
  }
  return []
}

export function boundaryLocalRing(
  twin: OrchardTwin,
  origin: { lat: number; lng: number },
): LocalPoint[] {
  return ringLatLngFromBoundary(twin.parcel.boundary).map(([lat, lng]) =>
    projectLatLng(lat, lng, origin.lat, origin.lng),
  )
}

export function pointInRing(x: number, y: number, ring: LocalPoint[]): boolean {
  if (ring.length < 3) return false
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i]!.x
    const yi = ring[i]!.y
    const xj = ring[j]!.x
    const yj = ring[j]!.y
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi
    if (intersect) inside = !inside
  }
  return inside
}

/** Nearest forward ray–edge hit (t > eps). Returns distance along the ray. */
function rayFirstExit(
  ox: number,
  oy: number,
  dx: number,
  dy: number,
  ring: LocalPoint[],
  eps = 1e-4,
): number | null {
  let best: number | null = null
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const ax = ring[j]!.x
    const ay = ring[j]!.y
    const bx = ring[i]!.x
    const by = ring[i]!.y
    const ex = bx - ax
    const ey = by - ay
    const denom = dx * ey - dy * ex
    if (Math.abs(denom) < 1e-12) continue
    const t = ((ax - ox) * ey - (ay - oy) * ex) / denom
    const u = ((ax - ox) * dy - (ay - oy) * dx) / denom
    if (t > eps && u >= -1e-6 && u <= 1 + 1e-6) {
      if (best === null || t < best) best = t
    }
  }
  return best
}

function normalize(dx: number, dy: number): LocalPoint {
  const len = Math.hypot(dx, dy)
  if (len < 1e-9) return { x: 0, y: 1 }
  return { x: dx / len, y: dy / len }
}

/**
 * Row labels just outside the parcel, all on one consistent side of the rows.
 * Casts along each row axis to the boundary exit — avoids edge-row labels
 * snapping onto the wrong (side) edge of the polygon.
 */
export function rowLabelLocals(
  trees: TreeMapItem[],
  boundary: LocalPoint[],
  gapM = 2.2,
): Array<{ rowNumber: number; x: number; y: number }> {
  const planted = trees.filter((t) => t.status !== 'removed')
  if (planted.length === 0) return []

  const cx =
    boundary.length >= 3
      ? boundary.reduce((s, p) => s + p.x, 0) / boundary.length
      : planted.reduce((s, t) => s + Number(t.normalized_x), 0) / planted.length
  const cy =
    boundary.length >= 3
      ? boundary.reduce((s, p) => s + p.y, 0) / boundary.length
      : planted.reduce((s, t) => s + Number(t.normalized_y), 0) / planted.length

  const byRow = new Map<number, Array<{ x: number; y: number; pos: number }>>()
  for (const tree of planted) {
    const list = byRow.get(tree.row_number) ?? []
    list.push({
      x: Number(tree.normalized_x),
      y: Number(tree.normalized_y),
      pos: tree.position_in_row,
    })
    byRow.set(tree.row_number, list)
  }

  type RowGeom = {
    rowNumber: number
    first: LocalPoint
    last: LocalPoint
    mid: LocalPoint
    /** Unit vector first → last */
    along: LocalPoint
  }
  const rows: RowGeom[] = []
  for (const [rowNumber, pts] of [...byRow.entries()].sort((a, b) => a[0] - b[0])) {
    const sorted = [...pts].sort((a, b) => a.pos - b.pos)
    const first = { x: sorted[0]!.x, y: sorted[0]!.y }
    const last = { x: sorted[sorted.length - 1]!.x, y: sorted[sorted.length - 1]!.y }
    const span = Math.hypot(last.x - first.x, last.y - first.y)
    const along =
      span < 1e-6
        ? normalize(first.x - cx, first.y - cy)
        : normalize(last.x - first.x, last.y - first.y)
    rows.push({
      rowNumber,
      first,
      last,
      mid: { x: (first.x + last.x) / 2, y: (first.y + last.y) / 2 },
      along,
    })
  }

  // Average row direction, flipped so it points toward the southern side of the parcel.
  let avgX = 0
  let avgY = 0
  for (const row of rows) {
    avgX += row.along.x
    avgY += row.along.y
  }
  let labelDir = normalize(avgX, avgY)
  // Score both orientations by mean exit Y (y grows south) — pick the more southern side.
  if (boundary.length >= 3) {
    let scorePos = 0
    let scoreNeg = 0
    let nPos = 0
    let nNeg = 0
    for (const row of rows) {
      const tPos = rayFirstExit(row.mid.x, row.mid.y, labelDir.x, labelDir.y, boundary)
      const tNeg = rayFirstExit(row.mid.x, row.mid.y, -labelDir.x, -labelDir.y, boundary)
      if (tPos != null) {
        scorePos += row.mid.y + labelDir.y * tPos
        nPos += 1
      }
      if (tNeg != null) {
        scoreNeg += row.mid.y - labelDir.y * tNeg
        nNeg += 1
      }
    }
    const meanPos = nPos > 0 ? scorePos / nPos : -Infinity
    const meanNeg = nNeg > 0 ? scoreNeg / nNeg : -Infinity
    if (meanNeg > meanPos) {
      labelDir = { x: -labelDir.x, y: -labelDir.y }
    }
  } else {
    // No boundary: prefer the end with larger mean Y.
    let scoreLast = 0
    let scoreFirst = 0
    for (const row of rows) {
      scoreLast += row.last.y
      scoreFirst += row.first.y
    }
    if (scoreFirst > scoreLast) {
      labelDir = { x: -labelDir.x, y: -labelDir.y }
    }
  }

  const out: Array<{ rowNumber: number; x: number; y: number }> = []
  for (const row of rows) {
    // Per-row direction aligned with the global label side (avoid 180° flips on short rows).
    let dir = row.along
    if (dir.x * labelDir.x + dir.y * labelDir.y < 0) {
      dir = { x: -dir.x, y: -dir.y }
    }
    // Blend slightly with average so nearly-degenerate rows still aim the right way.
    dir = normalize(dir.x * 0.75 + labelDir.x * 0.25, dir.y * 0.75 + labelDir.y * 0.25)

    let x: number
    let y: number
    if (boundary.length >= 3) {
      const exitT = rayFirstExit(row.mid.x, row.mid.y, dir.x, dir.y, boundary)
      if (exitT != null) {
        x = row.mid.x + dir.x * (exitT + gapM)
        y = row.mid.y + dir.y * (exitT + gapM)
      } else {
        // Already outside or grazing — step from the outer endpoint.
        const end =
          (row.last.x - row.mid.x) * dir.x + (row.last.y - row.mid.y) * dir.y >=
          (row.first.x - row.mid.x) * dir.x + (row.first.y - row.mid.y) * dir.y
            ? row.last
            : row.first
        x = end.x + dir.x * gapM
        y = end.y + dir.y * gapM
      }
      // Hard guarantee: never leave a label inside the frame.
      for (let i = 0; i < 24 && pointInRing(x, y, boundary); i++) {
        x += dir.x * gapM
        y += dir.y * gapM
      }
    } else {
      const end =
        (row.last.x - row.mid.x) * dir.x + (row.last.y - row.mid.y) * dir.y >=
        (row.first.x - row.mid.x) * dir.x + (row.first.y - row.mid.y) * dir.y
          ? row.last
          : row.first
      x = end.x + dir.x * gapM
      y = end.y + dir.y * gapM
    }
    out.push({ rowNumber: row.rowNumber, x, y })
  }
  return out
}

/** Lat/lng row labels outside the parcel polygon, next to each row. */
export function rowLabelLatLng(
  trees: Array<{ tree: TreeMapItem; lat: number; lng: number }>,
  ringLatLng: [number, number][],
): Array<{ rowNumber: number; lat: number; lng: number }> {
  const planted = trees.filter((t) => t.tree.status !== 'removed')
  if (planted.length === 0) return []

  const origin = {
    lat: Math.max(...planted.map((t) => t.lat)),
    lng: Math.min(...planted.map((t) => t.lng)),
  }
  const boundary = ringLatLng.map(([lat, lng]) => projectLatLng(lat, lng, origin.lat, origin.lng))
  const asTrees: TreeMapItem[] = planted.map(({ tree, lat, lng }) => {
    const local = projectLatLng(lat, lng, origin.lat, origin.lng)
    return {
      ...tree,
      normalized_x: String(local.x),
      normalized_y: String(local.y),
      latitude: String(lat),
      longitude: String(lng),
    }
  })
  const locals = rowLabelLocals(asTrees, boundary, 2.4)
  const mLat = 111_320
  const mLon = 111_320 * Math.cos((origin.lat * Math.PI) / 180)
  return locals.map((p) => ({
    rowNumber: p.rowNumber,
    lat: origin.lat - p.y / mLat,
    lng: origin.lng + p.x / mLon,
  }))
}
