/** Index colormap: red (low) → yellow → green (high), matching Process PNG stretches. */

export type IndexScaleId = 'ndvi' | 'ndre' | 'ndwi'

/** Must match backend INDEX_COLOR_STRETCH in copernicus.py */
export const STRETCH: Record<IndexScaleId, { vmin: number; vmax: number }> = {
  ndvi: { vmin: -0.2, vmax: 0.9 },
  ndre: { vmin: -0.1, vmax: 0.6 },
  ndwi: { vmin: -0.5, vmax: 0.2 },
}

function stretchToUnit(value: number, index: IndexScaleId): number {
  const { vmin, vmax } = STRETCH[index]
  return Math.max(0, Math.min(1, (value - vmin) / (vmax - vmin)))
}

export function indexToColor(value: number | null, index: IndexScaleId = 'ndvi'): string {
  if (value == null || Number.isNaN(value)) return '#cbd5e1'
  const t = stretchToUnit(value, index)
  if (t < 0.5) {
    const u = t / 0.5
    const r = 215
    const g = Math.round(35 + 185 * u)
    const b = 25
    return `rgb(${r},${g},${b})`
  }
  const u = (t - 0.5) / 0.5
  const r = Math.round(215 - 175 * u)
  const g = Math.round(220 - 55 * u)
  const b = Math.round(25 + 35 * u)
  return `rgb(${r},${g},${b})`
}

/** @deprecated Prefer indexToColor(value, 'ndvi') */
export function ndviToColor(value: number | null): string {
  return indexToColor(value, 'ndvi')
}

/** CSS continuous ramp (same endpoints as raster colormap). */
export function indexLegendGradient(index: IndexScaleId): string {
  const stops = [0, 0.25, 0.5, 0.75, 1].map((t) => {
    const { vmin, vmax } = STRETCH[index]
    const value = vmin + t * (vmax - vmin)
    return `${indexToColor(value, index)} ${(t * 100).toFixed(0)}%`
  })
  return `linear-gradient(90deg, ${stops.join(', ')})`
}

export const INDEX_LEGEND_STOPS: Record<IndexScaleId, { label: string; color: string }[]> = {
  ndvi: [
    { label: STRETCH.ndvi.vmin.toFixed(1), color: indexToColor(STRETCH.ndvi.vmin, 'ndvi') },
    { label: '0.2', color: indexToColor(0.2, 'ndvi') },
    { label: '0.4', color: indexToColor(0.4, 'ndvi') },
    { label: '0.6', color: indexToColor(0.6, 'ndvi') },
    { label: STRETCH.ndvi.vmax.toFixed(1), color: indexToColor(STRETCH.ndvi.vmax, 'ndvi') },
  ],
  ndre: [
    { label: STRETCH.ndre.vmin.toFixed(1), color: indexToColor(STRETCH.ndre.vmin, 'ndre') },
    { label: '0.15', color: indexToColor(0.15, 'ndre') },
    { label: '0.3', color: indexToColor(0.3, 'ndre') },
    { label: STRETCH.ndre.vmax.toFixed(1), color: indexToColor(STRETCH.ndre.vmax, 'ndre') },
  ],
  ndwi: [
    { label: STRETCH.ndwi.vmin.toFixed(1), color: indexToColor(STRETCH.ndwi.vmin, 'ndwi') },
    { label: '−0.3', color: indexToColor(-0.3, 'ndwi') },
    { label: '−0.1', color: indexToColor(-0.1, 'ndwi') },
    { label: STRETCH.ndwi.vmax.toFixed(1), color: indexToColor(STRETCH.ndwi.vmax, 'ndwi') },
  ],
}

/** @deprecated Prefer INDEX_LEGEND_STOPS.ndvi */
export const NDVI_LEGEND_STOPS = INDEX_LEGEND_STOPS.ndvi

export const NATIVE_RESOLUTION_LABELS: Record<IndexScaleId, string> = {
  ndvi: 'nativno ~10 m (B04, B08)',
  ndre: 'nativno ~20 m (B05, B8A)',
  ndwi: 'nativno 10–20 m (B08, B11)',
}
