/** Sutherland–Hodgman polygon clip. Points are [lng, lat]. */

type LngLat = [number, number]

function isInside(p: LngLat, a: LngLat, b: LngLat): boolean {
  // Left of directed edge a→b (for CCW clip rings).
  return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12
}

function edgeIntersection(p1: LngLat, p2: LngLat, a: LngLat, b: LngLat): LngLat {
  const x1 = p1[0]
  const y1 = p1[1]
  const x2 = p2[0]
  const y2 = p2[1]
  const x3 = a[0]
  const y3 = a[1]
  const x4 = b[0]
  const y4 = b[1]
  const den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
  if (Math.abs(den) < 1e-15) return p2
  const t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
  return [x1 + t * (x2 - x1), y1 + t * (y2 - y1)]
}

function clipAgainstEdge(subject: LngLat[], a: LngLat, b: LngLat): LngLat[] {
  if (subject.length === 0) return []
  const out: LngLat[] = []
  let prev = subject[subject.length - 1]!
  let prevInside = isInside(prev, a, b)
  for (const curr of subject) {
    const currInside = isInside(curr, a, b)
    if (currInside) {
      if (!prevInside) out.push(edgeIntersection(prev, curr, a, b))
      out.push(curr)
    } else if (prevInside) {
      out.push(edgeIntersection(prev, curr, a, b))
    }
    prev = curr
    prevInside = currInside
  }
  return out
}

function ensureClosed(ring: LngLat[]): LngLat[] {
  if (ring.length < 2) return ring
  const first = ring[0]!
  const last = ring[ring.length - 1]!
  if (first[0] === last[0] && first[1] === last[1]) return ring.slice(0, -1)
  return ring
}

function ringArea(ring: LngLat[]): number {
  let area = 0
  const n = ring.length
  for (let i = 0; i < n; i++) {
    const [x1, y1] = ring[i]!
    const [x2, y2] = ring[(i + 1) % n]!
    area += x1 * y2 - x2 * y1
  }
  return area / 2
}

/** Clip subject ring by clip ring. Both [lng, lat], open or closed. Returns open ring or []. */
export function clipPolygonByPolygon(subject: LngLat[], clip: LngLat[]): LngLat[] {
  let output = ensureClosed(subject)
  const clipRing = ensureClosed(clip)
  if (output.length < 3 || clipRing.length < 3) return []

  // Clip ring should be CCW for "inside = left of edge".
  const oriented = ringArea(clipRing) < 0 ? [...clipRing].reverse() : clipRing

  for (let i = 0; i < oriented.length; i++) {
    const a = oriented[i]!
    const b = oriented[(i + 1) % oriented.length]!
    output = clipAgainstEdge(output, a, b)
    if (output.length === 0) return []
  }
  return output
}

export function ringLngLatFromGeometry(geometry: Record<string, unknown> | null | undefined): LngLat[] | null {
  if (!geometry) return null
  const type = geometry.type
  const coordinates = geometry.coordinates as unknown
  let ring: number[][] | null = null
  if (type === 'Polygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    ring = coordinates[0] as number[][]
  } else if (type === 'MultiPolygon' && Array.isArray(coordinates) && Array.isArray(coordinates[0])) {
    const first = coordinates[0] as unknown[]
    if (Array.isArray(first) && Array.isArray(first[0])) ring = first[0] as number[][]
  }
  if (!ring || ring.length < 3) return null
  const out: LngLat[] = []
  for (const point of ring) {
    if (!Array.isArray(point) || point.length < 2) continue
    const lng = Number(point[0])
    const lat = Number(point[1])
    if (Number.isFinite(lng) && Number.isFinite(lat)) out.push([lng, lat])
  }
  return out.length >= 3 ? ensureClosed(out) : null
}
