import { tr } from '@/shared/i18n/i18n'
/** User-facing labels for satellite monitoring (never show raw API slugs). */

function anomalyKindLabels(): Record<string, string> {
  return {
    below_parcel_mean: tr('Slabije od ostatka parcele'),
    sudden_decline: tr('Naglo slabije nego pre'),
    persistent_low: tr('Slabije više snimaka zaredom'),
  }
}

export function anomalyKindLabel(kind: string): string {
  return anomalyKindLabels()[kind] ?? humanizeSlug(kind)
}

/** Prefer kind-based Serbian copy so old English DB messages stay readable. */
export function anomalyMessageLabel(
  kind: string,
  message: string,
  details?: Record<string, unknown> | null,
): string {
  switch (kind) {
    case 'below_parcel_mean':
      return tr('Na tom mestu biljke izgledaju slabije (manje zeleno) od ostatka parcele.')
    case 'sudden_decline':
      return tr('Na tom mestu biljke su naglo slabije nego na prethodnom snimku.')
    case 'persistent_low': {
      const raw = details?.consecutive_observations
      const n = typeof raw === 'number' ? raw : Number(raw)
      const count = Number.isFinite(n) && n >= 2 ? Math.trunc(n) : 2
      return tr('Isto mesto je slabije od ostatka parcele kroz {{count}} snimka zaredom.', { count })
    }
    default:
      if (message && !/[a-z]+_[a-z]+/.test(message) && !message.startsWith('Potential anomaly')) {
        return message
      }
      return anomalyKindLabel(kind)
  }
}

/** `r0c3` → tr("red 1, kolona 4") (1-based for people). Prefer tree IDs when available. */
export function zoneKeyLabel(zoneKey: string | null | undefined): string | null {
  if (!zoneKey) return null
  const match = /^r(\d+)c(\d+)$/i.exec(zoneKey.trim())
  if (match) {
    const row = Number(match[1]) + 1
    const col = Number(match[2]) + 1
    return tr('red {{row}}, kolona {{col}}', { row, col })
  }
  return humanizeSlug(zoneKey)
}

export function treeIdsLabel(
  treeIds: string[] | null | undefined,
  options?: { maxShow?: number },
): string | null {
  if (!treeIds?.length) return null
  const maxShow = options?.maxShow ?? 8
  const shown = treeIds.slice(0, maxShow)
  const extra = treeIds.length - shown.length
  return extra > 0 ? `${shown.join(', ')} (+${extra})` : shown.join(', ')
}

/** Prefer orchard tree public IDs; fall back to grid cell label. */
export function locationFromZone(
  zoneKey: string | null | undefined,
  treeIds?: string[] | null,
): string | null {
  return treeIdsLabel(treeIds) ?? zoneKeyLabel(zoneKey)
}

/** Replace leftover r3c0 keys in AI text with tree IDs or a plain phrase. */
export function humanizeZoneKeysInText(
  text: string,
  treeIds?: string[] | null,
): string {
  if (!text) return text
  const fallback = treeIdsLabel(treeIds, { maxShow: 3 }) ?? tr('deo parcele')
  return text.replace(/\br(\d+)c(\d+)\b/gi, fallback)
}

export function zoneTitle(zoneKey: string, treeIds?: string[] | null): string {
  const trees = treeIdsLabel(treeIds, { maxShow: 4 })
  if (trees) return tr('Stabla {{trees}}', { trees })
  const label = zoneKeyLabel(zoneKey)
  return label ? tr('Deo parcele ({{label}})', { label }) : tr('Deo parcele')
}

export function indexNameLabel(indexName: string): string {
  const key = indexName.trim().toLowerCase()
  if (key === 'ndvi') return tr('zelenilo biljaka (NDVI)')
  if (key === 'ndre') return tr('stanje krošnje (NDRE)')
  if (key === 'ndwi') return tr('vlaga / voda (NDWI)')
  return humanizeSlug(indexName)
}

function humanizeSlug(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^\w/, (ch) => ch.toUpperCase())
}
