import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { login } from '@/features/auth/api'
import { loginSchema, type LoginValues } from '@/features/auth/schemas'
import { getEnterpriseMe } from '@/features/enterprise/api'
import { LanguageSwitcher } from '@/shared/i18n/LanguageSwitcher'
import { tr } from '@/shared/i18n/i18n'
import { setAccessToken } from '@/shared/lib/auth'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { i18n } = useTranslation()
  void i18n.language
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
      try {
        const enterprise = await getEnterpriseMe()
        if (enterprise.must_change_password) {
          void navigate('/enterprise/change-password')
          return
        }
        if (enterprise.memberships.length > 0) {
          void navigate(`/enterprise/${enterprise.memberships[0]!.organization_id}`)
          return
        }
      } catch {
        // Not an Enterprise user — continue to producer home.
      }
      void navigate('/')
    },
  })

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden overflow-hidden bg-sidebar px-12 py-16 text-sidebar-foreground lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(90,173,69,0.18),transparent_36%),radial-gradient(circle_at_80%_70%,rgba(46,179,190,0.16),transparent_40%)]" />
        <div className="relative z-10 flex items-start justify-between gap-4">
          <BrandLogo className="w-[10.5rem] max-w-full" />
          <LanguageSwitcher />
        </div>
        <div className="relative z-10 max-w-md space-y-5">
          <h1 className="text-4xl font-semibold leading-tight">{tr('Voćnjak, stablo po stablo.')}</h1>
          <p className="text-sm leading-6 text-sidebar-foreground/75">
            {tr(
              'Radna platforma za upravljanje lesnikom. Svaka parcela, red i stablo nose svoju istoriju, troškove i evidenciju zdravlja.',
            )}
          </p>
        </div>
        <p className="relative z-10 text-xs font-medium tracking-wide text-sidebar-foreground/50">
          {tr('Zasadi lesnika')}
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-12 pt-[max(3rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))]">
        <form
          className="w-full max-w-sm space-y-6"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 lg:hidden">
              <BrandLogo className="w-[8.25rem] max-w-full" />
              <LanguageSwitcher className="border-border bg-muted/40 [&_button]:text-foreground [&_button]:hover:bg-muted" />
            </div>
            <div className="space-y-2">
              <p className="kicker">{tr('Prijava')}</p>
              <h2 className="text-2xl font-semibold">{tr('Nastavite u voćnjak')}</h2>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">{tr('E-pošta')}</Label>
            <Input id="email" type="email" autoComplete="email" {...form.register('email')} />
            {form.formState.errors.email ? (
              <p className="text-xs text-danger">{form.formState.errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">{tr('Lozinka')}</Label>
            <Input id="password" type="password" autoComplete="current-password" {...form.register('password')} />
            {form.formState.errors.password ? (
              <p className="text-xs text-danger">{form.formState.errors.password.message}</p>
            ) : null}
          </div>

          {mutation.error ? (
            <p className="text-sm text-danger">{mutation.error.message}</p>
          ) : null}

          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? tr('Prijava…') : tr('Prijavi se')}
          </Button>
        </form>
      </section>
    </div>
  )
}
