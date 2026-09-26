import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import { login } from '@/features/auth/api'
import { loginSchema, type LoginValues } from '@/features/auth/schemas'
import { setAccessToken } from '@/shared/lib/auth'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async (data) => {
      await queryClient.cancelQueries()
      queryClient.clear()
      setAccessToken(data.access_token)
      void navigate('/')
    },
  })

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden overflow-hidden bg-sidebar px-12 py-16 text-sidebar-foreground lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(90,173,69,0.18),transparent_36%),radial-gradient(circle_at_80%_70%,rgba(46,179,190,0.16),transparent_40%)]" />
        <BrandLogo className="relative z-10 w-[10.5rem] max-w-full" />
        <div className="relative z-10 max-w-md space-y-5">
          <h1 className="text-4xl font-semibold leading-tight">Voćnjak, stablo po stablo.</h1>
          <p className="text-sm leading-6 text-sidebar-foreground/75">
            Radna platforma za upravljanje lesnikom. Svaka parcela, red i stablo nose svoju istoriju,
            troškove i evidenciju zdravlja.
          </p>
        </div>
        <p className="relative z-10 text-xs font-medium tracking-wide text-sidebar-foreground/50">
          Zasadi lesnika
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-12 pt-[max(3rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))]">
        <form
          className="w-full max-w-sm space-y-6"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <div className="space-y-4">
            <BrandLogo className="w-[8.25rem] max-w-full lg:hidden" />
            <div className="space-y-2">
              <p className="kicker">Prijava</p>
              <h2 className="text-2xl font-semibold">Nastavite u voćnjak</h2>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">E-pošta</Label>
            <Input id="email" type="email" autoComplete="email" {...form.register('email')} />
            {form.formState.errors.email ? (
              <p className="text-xs text-danger">{form.formState.errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Lozinka</Label>
            <Input id="password" type="password" autoComplete="current-password" {...form.register('password')} />
            {form.formState.errors.password ? (
              <p className="text-xs text-danger">{form.formState.errors.password.message}</p>
            ) : null}
          </div>

          {mutation.error ? (
            <p className="text-sm text-danger">{mutation.error.message}</p>
          ) : null}

          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Prijava…' : 'Prijavi se'}
          </Button>
        </form>
      </section>
    </div>
  )
}
