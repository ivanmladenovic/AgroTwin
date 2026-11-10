import { z } from 'zod'

import { tr } from '@/shared/i18n/i18n'

export const loginSchema = z.object({
  email: z.string().email(tr('Unesite ispravnu e-poštu')),
  password: z.string().min(1, tr('Lozinka je obavezna')),
})

export type LoginValues = z.infer<typeof loginSchema>
