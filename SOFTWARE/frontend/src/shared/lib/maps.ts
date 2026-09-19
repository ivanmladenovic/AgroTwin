const ALLOWED_HOST_SUFFIXES = ['google.com', 'google.rs', 'goo.gl']

export function normalizeMapsUrl(value: string | null | undefined) {
  const text = value?.trim() ?? ''
  if (!text) return ''
  try {
    const parsed = new URL(text)
    let host = parsed.host.toLowerCase()
    if (host.startsWith('www.')) host = host.slice(4)
    const allowed = ALLOWED_HOST_SUFFIXES.some((suffix) => host === suffix || host.endsWith(`.${suffix}`))
    if (!['http:', 'https:'].includes(parsed.protocol) || !allowed) return null
    return text
  } catch {
    return null
  }
}

export function mapsUrlSchemaMessage() {
  return 'Unesite Google Maps link (maps.google.com ili maps.app.goo.gl)'
}

export function parcelCoordinates(parcel: { latitude: string | null; longitude: string | null }) {
  if (!parcel.latitude || !parcel.longitude) return null
  const lat = Number(parcel.latitude)
  const lng = Number(parcel.longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null
  return { lat, lng }
}
