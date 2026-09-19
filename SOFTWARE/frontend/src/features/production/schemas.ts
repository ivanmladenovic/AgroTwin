import { z } from 'zod'

export const harvestFormSchema = z
  .object({
    harvested_on: z.string().min(1, 'Izaberite datum'),
    scope_type: z.enum(['parcel', 'row', 'tree']),
    row_id: z.string().optional(),
    tree_id: z.string().optional(),
    gross_quantity: z.string().min(1, 'Unesite bruto količinu'),
    loss_quantity: z.string().optional(),
    unit: z.string().min(1),
    moisture_percent: z.string().optional(),
    quality_category: z.enum(['', 'premium', 'standard', 'lower', 'other']),
    damaged_percent: z.string().optional(),
    empty_nuts_percent: z.string().optional(),
    foreign_material_percent: z.string().optional(),
    size_or_caliber: z.string().optional(),
    notes: z.string().optional(),
  })
  .superRefine((values, context) => {
    const gross = Number(values.gross_quantity.replace(',', '.'))
    const loss = Number((values.loss_quantity || '0').replace(',', '.'))
    if (!Number.isFinite(gross) || gross <= 0) {
      context.addIssue({ code: 'custom', path: ['gross_quantity'], message: 'Bruto količina mora biti veća od nule' })
    }
    if (!Number.isFinite(loss) || loss < 0) {
      context.addIssue({ code: 'custom', path: ['loss_quantity'], message: 'Gubitak ne može biti negativan' })
    }
    if (Number.isFinite(gross) && Number.isFinite(loss) && loss > gross) {
      context.addIssue({ code: 'custom', path: ['loss_quantity'], message: 'Gubitak ne može biti veći od bruto količine' })
    }
    if (values.scope_type === 'row' && !values.row_id) {
      context.addIssue({ code: 'custom', path: ['row_id'], message: 'Izaberite red' })
    }
    if (values.scope_type === 'tree') {
      if (!values.row_id) context.addIssue({ code: 'custom', path: ['row_id'], message: 'Izaberite red' })
      if (!values.tree_id) context.addIssue({ code: 'custom', path: ['tree_id'], message: 'Izaberite stablo' })
    }
    for (const field of ['moisture_percent', 'damaged_percent', 'empty_nuts_percent', 'foreign_material_percent'] as const) {
      const raw = values[field]
      if (!raw) continue
      const numeric = Number(raw.replace(',', '.'))
      if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) {
        context.addIssue({ code: 'custom', path: [field], message: 'Unesite vrednost od 0 do 100' })
      }
    }
  })

export type HarvestFormValues = z.infer<typeof harvestFormSchema>
