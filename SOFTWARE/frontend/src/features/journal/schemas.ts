import { z } from 'zod'

export const activityLineItemSchema = z.object({
  quantity: z.string().optional(),
  unit: z.string().optional(),
})

export const activityFormSchema = z
  .object({
    activity_type_id: z.string().min(1, 'Izaberite tip aktivnosti'),
    performed_on: z.string().min(1, 'Izaberite datum'),
    scope_type: z.enum(['parcel', 'row', 'tree']),
    parcel_id: z.string().min(1, 'Parcela nije izabrana'),
    row_id: z.string().optional(),
    row_ids: z.array(z.string()).default([]),
    tree_id: z.string().optional(),
    description: z.string().optional(),
    line_items: z.array(activityLineItemSchema).min(1),
    status: z.enum(['planned', 'in_progress', 'completed', 'cancelled']),
  })
  .superRefine((values, context) => {
    if (values.scope_type === 'row' && values.row_ids.length === 0) {
      context.addIssue({ code: 'custom', path: ['row_ids'], message: 'Izaberite bar jedan red' })
    }
    if (values.scope_type === 'tree') {
      if (!values.row_id) context.addIssue({ code: 'custom', path: ['row_id'], message: 'Izaberite red' })
      if (!values.tree_id) context.addIssue({ code: 'custom', path: ['tree_id'], message: 'Izaberite stablo' })
    }
  })

export type ActivityFormValues = z.infer<typeof activityFormSchema>

export const costFormSchema = z.object({
  description: z.string().min(1, 'Unesite opis'),
  cost_category_id: z.string().min(1, 'Izaberite kategoriju'),
  amount: z.string().min(1, 'Unesite iznos'),
  currency: z.string().min(3).max(3),
  incurred_on: z.string().optional(),
  notes: z.string().optional(),
  receipt_filename: z.string().optional(),
})

export type CostFormValues = z.infer<typeof costFormSchema>
