import { useEffect, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getPublicPassport } from '@/features/passport/api'
import { PassportFacts } from '@/features/passport/PassportFacts'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'

import { tr } from '@/shared/i18n/i18n'
export function PassportPage() {
  const { token } = useParams()
  const passportQuery = useQuery({
    queryKey: ['public-passport', token],
    queryFn: () => getPublicPassport(token!),
    enabled: Boolean(token),
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: 'always',
  })

  const passport = passportQuery.data

  useEffect(() => {
    if (!passport) return
    const robots = document.querySelector('meta[name="robots"]')
    const content = passport.allow_indexing ? 'index,follow' : 'noindex,nofollow'
    if (robots) {
      robots.setAttribute('content', content)
    } else {
      const meta = document.createElement('meta')
      meta.name = 'robots'
      meta.content = content
      document.head.appendChild(meta)
    }
    document.title = tr('Digitalni pasoš · {{lot}}', { lot: passport.lot_number })
  }, [passport])

  if (!token) {
    return (
      <PassportShell>
        <p className="text-sm text-muted-foreground">{tr('Nedostaje token pasoša.')}</p>
      </PassportShell>
    )
  }

  if (passportQuery.isLoading) {
    return (
      <PassportShell>
        <p className="text-sm text-muted-foreground">{tr('Učitavanje pasoša…')}</p>
      </PassportShell>
    )
  }

  if (passportQuery.isError || !passport) {
    const message =
      passportQuery.error instanceof Error ? passportQuery.error.message : tr('Pasoš nije pronađen.')
    return (
      <PassportShell>
        <p className="text-sm text-danger">{message}</p>
        <Button variant="outline" size="sm" onClick={() => void passportQuery.refetch()}>
          {tr("Pokušaj ponovo")}
        </Button>
      </PassportShell>
    )
  }

  return (
    <PassportShell>
      <header className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {tr('Digitalni pasoš proizvoda')}
        </p>
      </header>
      <PassportFacts
        producer={passport.producer?.name}
        location={passport.orchard?.location}
        lotNumber={passport.lot_number}
        crop={passport.product?.crop}
        varieties={passport.product?.varieties ?? []}
        harvestDate={passport.product?.harvest_date}
      />
    </PassportShell>
  )
}

function PassportShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-gradient-to-b from-emerald-50/80 via-background to-background">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
        <div className="flex justify-center">
          <BrandLogo className="h-8 w-auto" />
        </div>
        <article className="space-y-6 rounded-2xl border border-border bg-card/95 p-5 shadow-sm sm:p-7">
          {children}
        </article>
        <p className="text-center text-xs text-muted-foreground">{tr('AgroTwin Digitalni pasoš proizvoda')}</p>
      </div>
    </div>
  )
}

