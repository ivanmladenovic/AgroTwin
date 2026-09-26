import type { CatalogItem } from '@/shared/api/types'
import type { ActivityLineItemValues } from '@/features/journal/schemas'

export type ActivityLineKind = 'irrigation' | 'spraying' | 'fertilization' | 'soil_analysis' | 'other'

export function activityLineKind(type: CatalogItem | undefined): ActivityLineKind {
  const slug = type?.slug
  if (slug === 'irrigation' || slug === 'spraying' || slug === 'fertilization' || slug === 'soil_analysis') return slug
  return 'other'
}

export function emptyActivityLineItem(kind: ActivityLineKind): ActivityLineItemValues {
  if (kind === 'irrigation') return emptyIrrigationFuelItem()
  if (kind === 'spraying') {
    return { name: '', quantity: '', unit: 'L', volume: '', volume_unit: '', amount: '' }
  }
  if (kind === 'fertilization') {
    return { name: '', quantity: '', unit: 'kg', volume: '', volume_unit: '', amount: '' }
  }
  return { name: '', quantity: '', unit: '', volume: '', volume_unit: '', amount: '' }
}

export function emptyIrrigationFuelItem(): ActivityLineItemValues {
  return { name: 'Nafta', quantity: '', unit: 'L', volume: '', volume_unit: '', amount: '' }
}

export function emptyIrrigationEquipmentItem(): ActivityLineItemValues {
  return { name: '', quantity: '', unit: 'kom', volume: '', volume_unit: '', amount: '' }
}

export function activityLineSectionLabel(kind: ActivityLineKind) {
  if (kind === 'irrigation') return 'Nafta'
  if (kind === 'spraying' || kind === 'fertilization') return 'Preparati'
  return 'Stavke'
}

export function isIrrigationFuelName(name: string | null | undefined) {
  const value = (name ?? '').trim().toLowerCase()
  return value === 'nafta' || value === 'dizel' || value === 'diesel' || value === 'gorivo'
}

export function parseOptionalNumber(value: string | undefined) {
  const trimmed = value?.trim()
  if (!trimmed) return null
  const numeric = Number(trimmed.replace(',', '.'))
  return Number.isFinite(numeric) ? numeric : null
}
