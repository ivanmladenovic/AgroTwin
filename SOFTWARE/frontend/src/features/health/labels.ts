import type { DiseaseCategory, DiseaseSeverity, DiseaseStatus } from '@/shared/api/types'

export const diseaseCategories: Array<{ value: DiseaseCategory; label: string }> = [
  { value: 'disease', label: 'Bolest' },
  { value: 'pest', label: 'Štetočina' },
  { value: 'nutrient_deficiency', label: 'Nedostatak hraniva' },
  { value: 'water_stress', label: 'Vodni stres' },
  { value: 'physical_damage', label: 'Fizičko oštećenje' },
  { value: 'unknown', label: 'Nepoznato' },
  { value: 'other', label: 'Drugo' },
]

export const diseaseStatuses: Array<{ value: DiseaseStatus; label: string }> = [
  { value: 'open', label: 'Otvoreno' },
  { value: 'monitoring', label: 'Praćenje' },
  { value: 'resolved', label: 'Rešeno' },
  { value: 'unknown', label: 'Nepoznato' },
]

export const diseaseSeverities: Array<{ value: DiseaseSeverity; label: string }> = [
  { value: 'low', label: 'Nisko' },
  { value: 'medium', label: 'Srednje' },
  { value: 'high', label: 'Visoko' },
  { value: 'critical', label: 'Kritično' },
]

export function categoryLabel(value: string) {
  return diseaseCategories.find((item) => item.value === value)?.label ?? value
}

export function statusLabel(value: string) {
  return diseaseStatuses.find((item) => item.value === value)?.label ?? value
}

export function severityLabel(value: string) {
  return diseaseSeverities.find((item) => item.value === value)?.label ?? value
}
