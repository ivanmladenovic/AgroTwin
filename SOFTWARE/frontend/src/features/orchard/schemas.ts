import { z } from 'zod'

import { mapsUrlSchemaMessage, normalizeMapsUrl } from '@/shared/lib/maps'

export const varietySchema = z.object({
  name: z.string().min(1, 'Naziv sorte je obavezan').max(128),
  role: z.enum(['main', 'pollinator', 'other']),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, 'Izaberite boju'),
})

export const createParcelSchema = z
  .object({
    name: z.string().min(1, 'Naziv parcele je obavezan').max(255),
    area_hectares: z.coerce.number().positive('Površina mora biti veća od 0'),
    row_count: z.coerce.number().int().min(1).max(200),
    trees_per_row: z.coerce.number().int().min(1).max(500),
    row_spacing_m: z.coerce.number().positive('Razmak redova mora biti veći od 0'),
    tree_spacing_m: z.coerce.number().positive('Razmak sadnica mora biti veći od 0'),
    planting_year: z.coerce.number().int().min(1900).max(2100),
    starting_tree_number: z.coerce.number().int().min(1),
    maps_url: z
      .string()
      .trim()
      .optional()
      .refine((value) => value == null || value === '' || normalizeMapsUrl(value) !== null, mapsUrlSchemaMessage()),
    varieties: z.array(varietySchema).min(1, 'Dodajte bar jednu zasađenu sortu'),
  })
  .superRefine((data, ctx) => {
    const names = data.varieties.map((item) => item.name.trim().toLowerCase())
    if (new Set(names).size !== names.length) {
      ctx.addIssue({ code: 'custom', message: 'Nazivi sorti moraju biti jedinstveni', path: ['varieties'] })
    }
  })

export type CreateParcelValues = z.infer<typeof createParcelSchema>
export type VarietyValues = z.infer<typeof varietySchema>

export const editParcelSchema = z
  .object({
    name: z.string().min(1, 'Naziv parcele je obavezan').max(255),
    area_hectares: z.coerce.number().positive('Površina mora biti veća od 0'),
    planting_year: z.coerce.number().int().min(1900).max(2100),
    maps_url: z
      .string()
      .trim()
      .optional()
      .refine((value) => value == null || value === '' || normalizeMapsUrl(value) !== null, mapsUrlSchemaMessage()),
    varieties: z.array(varietySchema).min(1, 'Dodajte bar jednu zasađenu sortu'),
  })
  .superRefine((data, ctx) => {
    const names = data.varieties.map((item) => item.name.trim().toLowerCase())
    if (new Set(names).size !== names.length) {
      ctx.addIssue({ code: 'custom', message: 'Nazivi sorti moraju biti jedinstveni', path: ['varieties'] })
    }
  })

export type EditParcelValues = z.infer<typeof editParcelSchema>
