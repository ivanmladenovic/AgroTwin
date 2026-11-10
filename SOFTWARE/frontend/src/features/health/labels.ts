import type { DiseaseCategory, DiseaseSeverity, DiseaseStatus } from '@/shared/api/types'
import { tr } from '@/shared/i18n/i18n'

export function diseaseCategories(): Array<{ value: DiseaseCategory; label: string }> {
  return [
    { value: 'disease', label: tr('Bolest') },
    { value: 'pest', label: tr('Štetočina') },
    { value: 'nutrient_deficiency', label: tr('Nedostatak hraniva') },
    { value: 'water_stress', label: tr('Vodni stres') },
    { value: 'physical_damage', label: tr('Fizičko oštećenje') },
    { value: 'unknown', label: tr('Nepoznato') },
    { value: 'other', label: tr('Drugo') },
  ]
}

export function diseaseStatuses(): Array<{ value: DiseaseStatus; label: string }> {
  return [
    { value: 'open', label: tr('Otvoreno') },
    { value: 'monitoring', label: tr('Praćenje') },
    { value: 'resolved', label: tr('Rešeno') },
    { value: 'unknown', label: tr('Nepoznato') },
  ]
}

export function diseaseSeverities(): Array<{ value: DiseaseSeverity; label: string }> {
  return [
    { value: 'low', label: tr('Nisko') },
    { value: 'medium', label: tr('Srednje') },
    { value: 'high', label: tr('Visoko') },
    { value: 'critical', label: tr('Kritično') },
  ]
}

export function categoryLabel(value: string) {
  return diseaseCategories().find((item) => item.value === value)?.label ?? value
}

export function statusLabel(value: string) {
  return diseaseStatuses().find((item) => item.value === value)?.label ?? value
}

export function severityLabel(value: string) {
  return diseaseSeverities().find((item) => item.value === value)?.label ?? value
}
