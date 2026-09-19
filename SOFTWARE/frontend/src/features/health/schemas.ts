import { z } from 'zod'

export const reportProblemSchema = z.object({
  title: z.string().min(1, 'Unesite naslov'),
  category: z.enum([
    'disease',
    'pest',
    'nutrient_deficiency',
    'water_stress',
    'physical_damage',
    'unknown',
    'other',
  ]),
  severity: z.enum(['low', 'medium', 'high', 'critical']),
  status: z.enum(['open', 'monitoring', 'resolved', 'unknown']),
  detected_on: z.string().min(1),
  parcel_id: z.string().min(1, 'Izaberite parcelu'),
  row_id: z.string().optional(),
  tree_id: z.string().optional(),
  description: z.string().optional(),
  symptoms: z.string().optional(),
  notes: z.string().optional(),
})

export type ReportProblemValues = z.infer<typeof reportProblemSchema>
