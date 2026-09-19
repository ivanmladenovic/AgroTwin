import type { HarvestQualityCategory, HarvestScope } from '@/shared/api/types'

export const harvestQualityOptions: Array<{ value: HarvestQualityCategory | ''; label: string }> = [
  { value: '', label: 'Nije uneto' },
  { value: 'premium', label: 'Premijum' },
  { value: 'standard', label: 'Standard' },
  { value: 'lower', label: 'Niži kvalitet' },
  { value: 'other', label: 'Drugo' },
]

export function qualityLabel(value: HarvestQualityCategory | string | null | undefined) {
  if (!value) return '—'
  return harvestQualityOptions.find((item) => item.value === value)?.label ?? value
}

export function harvestScopeLabel(scope: HarvestScope | string) {
  if (scope === 'parcel') return 'Cela parcela'
  if (scope === 'row') return 'Red'
  if (scope === 'tree') return 'Stablo'
  return scope
}
