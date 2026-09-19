import type { ParcelVariety, VarietyRole } from '@/shared/api/types'

export const DEFAULT_VARIETIES: ParcelVariety[] = [
  { name: 'Tonda di Giffoni', role: 'main', color: '#DC2626' },
  { name: 'Tonda Gentile Romana', role: 'pollinator', color: '#16A34A' },
  { name: 'Nocchione', role: 'pollinator', color: '#2563EB' },
]

const extraColors = ['#7C3AED', '#CA8A04', '#0F766E', '#EA580C', '#475569']

export function nextVarietyColor(existing: ParcelVariety[]) {
  const used = new Set(existing.map((item) => item.color.toUpperCase()))
  return extraColors.find((color) => !used.has(color.toUpperCase())) ?? extraColors[existing.length % extraColors.length]
}

export function mainVarietyName(varieties: ParcelVariety[]) {
  return varieties.find((item) => item.role === 'main')?.name ?? varieties[0]?.name ?? DEFAULT_VARIETIES[0].name
}

export function varietyColorMap(varieties: ParcelVariety[] | undefined | null) {
  const map = new Map<string, string>()
  for (const item of varieties ?? []) {
    map.set(item.name, item.color)
  }
  return map
}

export function roleLabel(role: VarietyRole) {
  if (role === 'main') return 'Glavna sorta'
  if (role === 'pollinator') return 'Oprašivač'
  return 'Drugo'
}

export function varietiesFromTwin(twin: {
  parcel: { varieties?: ParcelVariety[]; default_variety: string | null }
  trees: Array<{ variety: string | null }>
}): ParcelVariety[] {
  if (twin.parcel.varieties && twin.parcel.varieties.length > 0) return twin.parcel.varieties
  const names = [...new Set(twin.trees.map((tree) => tree.variety).filter((name): name is string => Boolean(name)))]
  if (names.length === 0) {
    return twin.parcel.default_variety
      ? [{ name: twin.parcel.default_variety, role: 'main', color: '#DC2626' }]
      : DEFAULT_VARIETIES
  }
  return names.map((name, index) => ({
    name,
    role: index === 0 ? 'main' : 'pollinator',
    color: DEFAULT_VARIETIES[index]?.color ?? extraColors[index % extraColors.length],
  }))
}
