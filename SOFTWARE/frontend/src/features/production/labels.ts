import type { HarvestQualityCategory, HarvestScope } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export function harvestQualityOptions(): Array<{ value: HarvestQualityCategory | ''; label: string }> {
  return [
    { value: '', label: tr('Nije uneto') },
    { value: 'premium', label: tr('Premijum') },
    { value: 'standard', label: tr('Standard') },
    { value: 'lower', label: tr('Niži kvalitet') },
    { value: 'other', label: tr('Drugo') },
  ]
}

export function qualityLabel(value: HarvestQualityCategory | string | null | undefined) {
  if (!value) return '—'
  return harvestQualityOptions().find((item) => item.value === value)?.label ?? value
}

export function harvestScopeLabel(scope: HarvestScope | string) {
  if (scope === 'parcel') return tr('Cela parcela')
  if (scope === 'row') return tr('Red')
  if (scope === 'tree') return tr('Stablo')
  return scope
}
