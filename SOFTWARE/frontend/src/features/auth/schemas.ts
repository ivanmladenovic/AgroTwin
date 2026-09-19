import { z } from 'zod'

export const loginSchema = z.object({
  email: z.string().email('Unesite ispravnu e-poštu'),
  password: z.string().min(1, 'Lozinka je obavezna'),
})

export type LoginValues = z.infer<typeof loginSchema>
