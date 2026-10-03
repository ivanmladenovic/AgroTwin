import { z } from 'zod'

export const reportProblemSchema = z
  .object({
    title: z.string().optional(),
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
    scope: z.enum(['tree', 'trees', 'row']),
    row_id: z.string().optional(),
    tree_id: z.string().optional(),
    tree_ids: z.array(z.string()).optional(),
    description: z.string().optional(),
    symptoms: z.string().min(1, 'Opišite simptome'),
    notes: z.string().optional(),
  })
  .superRefine((values, context) => {
    if (values.scope === 'row' && !values.row_id) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: 'Izaberite red', path: ['row_id'] })
    }
    if (values.scope === 'tree' && !values.tree_id) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: 'Izaberite sadnicu', path: ['tree_id'] })
    }
    if (values.scope === 'trees' && !(values.tree_ids && values.tree_ids.length > 0)) {
      context.addIssue({ code: z.ZodIssueCode.custom, message: 'Izaberite bar jednu sadnicu', path: ['tree_ids'] })
    }
  })
  .transform((values) => {
    const symptoms = values.symptoms.trim()
    const title = (values.title || '').trim() || symptoms.slice(0, 80) || 'Prijavljen problem'
    return {
      ...values,
      title,
      symptoms,
      description: values.description?.trim() || undefined,
      notes: values.notes?.trim() || undefined,
    }
  })

export type ReportProblemValues = z.input<typeof reportProblemSchema>
export type ReportProblemParsed = z.output<typeof reportProblemSchema>
