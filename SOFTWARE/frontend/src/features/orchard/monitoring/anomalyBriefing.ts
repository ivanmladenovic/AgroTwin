import { treeIdsLabel } from '@/features/orchard/monitoring/satelliteLabels'
import type { SatelliteAnomaly, SatelliteZone } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
export type AnomalyBriefing = {
  /** Dominant anomaly kind driving the copy. */
  kind: string
  /** Approximate place on the parcel, e.g. tr("severozapadni deo parcele"). */
  locationLabel: string
  observed: string
  meaning: string
  impact: string
  actions: string[]
  affectedZoneCount: number
}

type KindCopy = {
  observed: string
  meaning: string
  impact: string
  actions: string[]
}

const KIND_COPY: Record<string, KindCopy> = {
  below_parcel_mean: {
    observed:
      tr('Na tom delu parcele biljke izgledaju slabije od ostatka zasada — više žuto, narandžasto ili crvenkasto, a manje zeleno.'),
    meaning:
      tr('Zelenije = bujnije i jače sadnice. Žuto / narandžasto / crveno = manje bujne, sitnije ili slabije od proseka parcele na dan snimka. To nije bolest „sa satelita“, već znak: „ovde proverite prvo“.'),
    impact:
      tr('Ako je na terenu stvarno tako, te sadnice mogu da zaostaju u rastu i kasnije daju manje prinosa od susednih, jačih biljaka.'),
    actions: [
      tr('Obiđite taj deo parcele i pogledajte da li su biljke stvarno manje ili slabije od ostatka.'),
      tr('Uporedite listove: da li su svetliji, suvlji, oštećeni ili ih ima manje.'),
      tr('Proverite da li tamo stiže voda isto kao na zelenijim delovima, i da li ima vidljivih štetočina ili oštećenja.'),
      tr('Ako vidite jasan problem, snimite fotografiju i prijavite problem u aplikaciji.'),
    ],
  },
  sudden_decline: {
    observed:
      tr('Na tom delu parcele biljke su na novom snimku izgledale znatno slabije nego na prethodnom — boja je otišla ka žutom / narandžastom.'),
    meaning:
      tr('Zelenije znači jača vegetacija. Nagli pad ka narandžastom/crvenom znači da je taj deo slabiji u odnosu na prošli snimak — biljke tamo deluju manje bujno. Ponekad snimak „laže“ zbog oblaka, zato proverite očima.'),
    impact:
      tr('Ako se potvrdi na terenu, biljke su možda pod iznenadnim stresom (voda, oštećenje, napad) i mogu brzo da oslabe.'),
    actions: [
      tr('Obiđite taj deo parcele i uporedite sa onim što pamtište od nedavne šetnje.'),
      tr('Pogledajte da li je nešto novo: suvo tlo, polomljene grane, tragovi štetočina, problem sa crevom za zalivanje.'),
      tr('Ako izgleda loše, odmah zabeležite problem sa fotografijom.'),
    ],
  },
  persistent_low: {
    observed:
      tr('Isti deo parcele više snimaka zaredom ostaje žutiji / narandžastiji od ostatka — slabije od proseka.'),
    meaning:
      tr('Zelenije = bujnije. Ako isti deo dugo ostaje narandžast/crven, verovatno nije greška jednog snimka: sadnice tamo su trajno manje bujne od ostatka voćnjaka.'),
    impact:
      tr('Takav deo često zaostaje u rastu i može da ostane slabiji i manje produktivan ako se ne proveri i ne popravi uzrok (voda, tlo, štetočine…).'),
    actions: [
      tr('Obiđite taj deo i uporedite veličinu i kondiciju sadnica sa zelenijim delovima.'),
      tr('Proverite vodu, tlo i da li nešto stalno smeta baš tu (senka, zbijeno tlo, loša cev…).'),
      tr('Ako potvrdite razliku, prijavite problem da pratite taj deo kroz sezonu.'),
    ],
  },
}

const FALLBACK_COPY: KindCopy = {
  observed:
    tr('Na delu parcele satelit pokazuje slabiji signal (više žuto/narandžasto) od ostatka zasada.'),
  meaning:
    tr('Zelenije = bujnije biljke. Narandžasto/crveno = slabije ili sitnije. Fokus stavite na te slabije delove, ne na zelene.'),
  impact:
    tr('Ako je tačno na terenu, te sadnice mogu da rastu sporije i daju manje od jačih delova parcele.'),
  actions: [
    tr('Obiđite taj deo parcele i uporedite biljke sa zelenijim delovima.'),
    tr('Proverite vodu, oštećenja i štetočine.'),
    tr('Po potrebi prijavite problem sa fotografijom.'),
  ],
}

/** Aggregate zone-level anomalies into one farmer-facing briefing. */
export function aggregateAnomalyBriefing(
  anomalies: SatelliteAnomaly[],
  zones: SatelliteZone[] = [],
): AnomalyBriefing | null {
  if (anomalies.length === 0) return null

  const kind = pickDominantKind(anomalies)
  const copy = KIND_COPY[kind] ?? FALLBACK_COPY
  const zoneKeys = uniqueZoneKeys(anomalies)
  const treeIds = uniqueTreeIds(anomalies, zones, zoneKeys)
  const treeLabel = treeIdsLabel(treeIds, { maxShow: 6 })
  const placeLabel = treeLabel
    ? tr('stabla {{trees}}', { trees: treeLabel })
    : approximateLocationLabel(zoneKeys, zones)

  return {
    kind,
    locationLabel: placeLabel,
    observed: copy.observed,
    meaning: copy.meaning,
    impact: copy.impact,
    actions: copy.actions,
    affectedZoneCount: zoneKeys.length,
  }
}

function uniqueTreeIds(
  anomalies: SatelliteAnomaly[],
  zones: SatelliteZone[],
  zoneKeys: string[],
): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const item of anomalies) {
    for (const id of item.tree_public_ids ?? []) {
      if (!id || seen.has(id)) continue
      seen.add(id)
      out.push(id)
    }
  }
  if (out.length) return out
  const zoneByKey = new Map(zones.map((z) => [z.zone_key, z]))
  for (const key of zoneKeys) {
    for (const id of zoneByKey.get(key)?.tree_public_ids ?? []) {
      if (!id || seen.has(id)) continue
      seen.add(id)
      out.push(id)
    }
  }
  return out
}

function pickDominantKind(anomalies: SatelliteAnomaly[]): string {
  const score = new Map<string, number>()
  for (const item of anomalies) {
    const severity = Number(item.severity)
    const weight = Number.isFinite(severity) ? Math.max(severity, 0.01) : 0.5
    score.set(item.kind, (score.get(item.kind) ?? 0) + weight)
  }
  const priority = ['persistent_low', 'sudden_decline', 'below_parcel_mean']
  let best = anomalies[0]?.kind ?? 'below_parcel_mean'
  let bestScore = -1
  for (const [kind, value] of score) {
    const boost = priority.includes(kind) ? (3 - priority.indexOf(kind)) * 0.01 : 0
    const total = value + boost
    if (total > bestScore) {
      bestScore = total
      best = kind
    }
  }
  return best
}

function uniqueZoneKeys(anomalies: SatelliteAnomaly[]): string[] {
  const keys: string[] = []
  const seen = new Set<string>()
  for (const item of anomalies) {
    if (!item.zone_key || seen.has(item.zone_key)) continue
    seen.add(item.zone_key)
    keys.push(item.zone_key)
  }
  return keys
}

type Point = { lon: number; lat: number }

function approximateLocationLabel(zoneKeys: string[], zones: SatelliteZone[]): string {
  if (zoneKeys.length === 0) return tr('deo parcele')

  const zoneByKey = new Map(zones.map((z) => [z.zone_key, z]))
  const centers: Point[] = []
  for (const key of zoneKeys) {
    const zone = zoneByKey.get(key)
    const center = zone ? geometryCentroid(zone.geometry) : parseZoneKeyCenter(key)
    if (center) centers.push(center)
  }

  if (centers.length === 0) {
    const fromKeys = zoneKeys.map(parseZoneKeyCenter).filter(Boolean) as Point[]
    if (fromKeys.length === 0) return tr('deo parcele')
    return describeRelativeRegions(fromKeys, fromKeys)
  }

  const allCenters =
    zones.length > 0
      ? (zones.map((z) => geometryCentroid(z.geometry)).filter(Boolean) as Point[])
      : centers
  const ref = allCenters.length > 0 ? allCenters : centers

  return describeRelativeRegions(centers, ref)
}

function describeRelativeRegions(affected: Point[], reference: Point[]): string {
  const bbox = pointsBBox(reference)
  if (!bbox) return tr('deo parcele')

  const regions = new Set<string>()
  for (const point of affected) {
    regions.add(compassRegion(point, bbox))
  }

  const ordered = orderRegions([...regions])
  if (ordered.length === 0) return tr('deo parcele')
  if (ordered.length === 1) {
    const region = ordered[0]!
    return region === 'središte' ? tr('središte parcele') : tr('{{region}} deo parcele', { region: tr(region) })
  }
  if (ordered.length === 2) {
    return tr('{{first}} i {{second}} deo parcele', {
      first: tr(ordered[0]!),
      second: tr(ordered[1]!),
    })
  }
  return tr('više delova parcele ({{regions}})', {
    regions: ordered
      .slice(0, 3)
      .map((key) => tr(key))
      .join(', '),
  })
}

type BBox = { minLon: number; maxLon: number; minLat: number; maxLat: number }

function pointsBBox(points: Point[]): BBox | null {
  if (points.length === 0) return null
  let minLon = points[0].lon
  let maxLon = points[0].lon
  let minLat = points[0].lat
  let maxLat = points[0].lat
  for (const p of points) {
    minLon = Math.min(minLon, p.lon)
    maxLon = Math.max(maxLon, p.lon)
    minLat = Math.min(minLat, p.lat)
    maxLat = Math.max(maxLat, p.lat)
  }
  return { minLon, maxLon, minLat, maxLat }
}

function compassRegion(point: Point, bbox: BBox): string {
  const width = Math.max(bbox.maxLon - bbox.minLon, 1e-9)
  const height = Math.max(bbox.maxLat - bbox.minLat, 1e-9)
  const x = (point.lon - bbox.minLon) / width
  const y = (point.lat - bbox.minLat) / height

  if (x > 0.35 && x < 0.65 && y > 0.35 && y < 0.65) return tr('središte')

  const ew = x < 0.4 ? 'zapad' : x > 0.6 ? 'istok' : ''
  const ns = y < 0.4 ? 'jug' : y > 0.6 ? 'sever' : ''

  if (ns && ew) {
    if (ns === 'sever' && ew === 'zapad') return 'severozapadni'
    if (ns === 'sever' && ew === 'istok') return tr('severoistočni')
    if (ns === 'jug' && ew === 'zapad') return 'jugozapadni'
    if (ns === 'jug' && ew === 'istok') return tr('jugoistočni')
  }
  if (ns === 'sever') return 'severni'
  if (ns === 'jug') return tr('južni')
  if (ew === 'zapad') return 'zapadni'
  if (ew === 'istok') return tr('istočni')
  return tr('središte')
}

const REGION_ORDER = [
  'severni',
  'severozapadni',
  tr('severoistočni'),
  'zapadni',
  tr('središte'),
  tr('istočni'),
  'jugozapadni',
  tr('jugoistočni'),
  tr('južni'),
]

function orderRegions(regions: string[]): string[] {
  return regions.sort((a, b) => REGION_ORDER.indexOf(a) - REGION_ORDER.indexOf(b))
}

function geometryCentroid(geometry: Record<string, unknown> | null | undefined): Point | null {
  if (!geometry) return null
  const coords: Point[] = []
  collectCoords(geometry, coords)
  if (coords.length === 0) return null
  const lon = coords.reduce((sum, p) => sum + p.lon, 0) / coords.length
  const lat = coords.reduce((sum, p) => sum + p.lat, 0) / coords.length
  return { lon, lat }
}

function collectCoords(geometry: Record<string, unknown>, out: Point[]) {
  const type = geometry.type
  const coordinates = geometry.coordinates
  if (type === 'Polygon' && Array.isArray(coordinates)) {
    const ring = coordinates[0]
    if (Array.isArray(ring)) pushRing(ring, out)
  } else if (type === 'MultiPolygon' && Array.isArray(coordinates)) {
    for (const poly of coordinates) {
      if (!Array.isArray(poly) || !Array.isArray(poly[0])) continue
      pushRing(poly[0], out)
    }
  } else if (type === 'Point' && Array.isArray(coordinates) && coordinates.length >= 2) {
    out.push({ lon: Number(coordinates[0]), lat: Number(coordinates[1]) })
  }
}

function pushRing(ring: unknown[], out: Point[]) {
  for (const point of ring) {
    if (!Array.isArray(point) || point.length < 2) continue
    const lon = Number(point[0])
    const lat = Number(point[1])
    if (Number.isFinite(lon) && Number.isFinite(lat)) out.push({ lon, lat })
  }
}

function parseZoneKeyCenter(zoneKey: string): Point | null {
  const match = /^r(\d+)c(\d+)$/i.exec(zoneKey.trim())
  if (!match) return null
  return { lon: Number(match[2]) + 0.5, lat: Number(match[1]) + 0.5 }
}
