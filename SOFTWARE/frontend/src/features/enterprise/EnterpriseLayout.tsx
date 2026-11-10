import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'

import { EnterpriseProvider, useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { getCurrentUser } from '@/features/auth/api'
import { LanguageSwitcher } from '@/shared/i18n/LanguageSwitcher'
import { clearAccessToken } from '@/shared/lib/auth'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Button } from '@/shared/ui/button'
import { Separator } from '@/shared/ui/separator'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'

/** Serbian source keys — translate with tr() at render so language switches apply. */
const navItemDefs = [
  { to: '', labelKey: 'Pregled', end: true },
  { to: 'suppliers', labelKey: 'Dobavljači', end: false },
  { to: 'parcels', labelKey: 'Parcele', end: false },
  { to: 'production', labelKey: 'Proizvodnja i prinos', end: false },
  { to: 'risks', labelKey: 'Aktivnosti i rizici', end: false },
  { to: 'reports', labelKey: 'Izveštaji', end: false },
  { to: 'settings', labelKey: 'Podešavanja', end: false },
]

export function EnterpriseLayout() {
  return (
    <EnterpriseProvider>
      <EnterpriseShell />
    </EnterpriseProvider>
  )
}

function EnterpriseShell() {
  const navigate = useNavigate()
  const { organizationId } = useParams()
  const { organization } = useEnterprise()
  const { i18n } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const userQuery = useQuery({ queryKey: ['me'], queryFn: getCurrentUser })
  void i18n.language

  useEffect(() => {
    setMenuOpen(false)
  }, [organizationId])

  function handleSignOut() {
    clearAccessToken()
    void navigate('/login')
  }

  const base = `/enterprise/${organizationId}`
  const orgName = organization?.name ?? 'Enterprise'

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden print:block print:h-auto print:max-h-none print:overflow-visible lg:flex-row">
      <header className="flex shrink-0 items-center justify-between gap-3 bg-sidebar px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-sidebar-foreground print:hidden lg:hidden">
        <NavLink to={base} className="min-w-0">
          <p className="truncate text-sm font-semibold">{orgName}</p>
          <p className="text-[10px] uppercase tracking-wider text-sidebar-foreground/60">Enterprise</p>
        </NavLink>
        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg hover:bg-white/10"
          aria-label={tr('Otvori meni')}
          onClick={() => setMenuOpen(true)}
        >
          <Menu className="h-6 w-6" />
        </button>
      </header>

      <aside className="relative hidden w-64 shrink-0 flex-col overflow-hidden bg-sidebar text-sidebar-foreground print:hidden lg:flex">
        <div className="px-5 pb-3 pt-6">
          <BrandLogo className="w-[7.5rem] max-w-full opacity-90" />
          <p className="mt-4 text-sm font-semibold leading-snug">{orgName}</p>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-foreground/55">
            {tr('Enterprise prostor')}
          </p>
        </div>
        <Separator className="bg-white/10" />
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {navItemDefs.map((item) => (
            <NavLink
              key={item.to || 'home'}
              to={item.to ? `${base}/${item.to}` : base}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'block rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground/80 hover:bg-white/10',
                  isActive && 'bg-white/15 text-sidebar-foreground',
                )
              }
            >
              {tr(item.labelKey)}
            </NavLink>
          ))}
        </nav>
        <div className="space-y-2 border-t border-white/10 px-4 py-4">
          <LanguageSwitcher />
          <p className="truncate text-xs text-sidebar-foreground/70">
            {userQuery.data?.full_name ?? '…'}
          </p>
          <Button type="button" variant="outline" className="w-full" onClick={handleSignOut}>
            {tr('Odjava')}
          </Button>
        </div>
      </aside>

      {menuOpen ? (
        <div className="fixed inset-0 z-[2000] print:hidden lg:hidden">
          <button type="button" className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <aside className="relative flex h-full w-[min(20rem,86vw)] flex-col bg-sidebar text-sidebar-foreground shadow-xl">
            <div className="flex items-center justify-between px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
              <p className="font-semibold">{orgName}</p>
              <button type="button" className="h-11 w-11 rounded-lg hover:bg-white/10" onClick={() => setMenuOpen(false)}>
                <X className="mx-auto h-6 w-6" />
              </button>
            </div>
            <div className="px-4 pb-2">
              <LanguageSwitcher />
            </div>
            <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
              {navItemDefs.map((item) => (
                <NavLink
                  key={item.to || 'home-m'}
                  to={item.to ? `${base}/${item.to}` : base}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'block rounded-lg px-3 py-2.5 text-sm font-medium',
                      isActive ? 'bg-white/15' : 'hover:bg-white/10',
                    )
                  }
                >
                  {tr(item.labelKey)}
                </NavLink>
              ))}
            </nav>
          </aside>
        </div>
      ) : null}

      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-background print:block print:h-auto print:max-h-none print:overflow-visible">
        <div
          key={i18n.language}
          className="mx-auto flex min-h-full w-full max-w-6xl flex-col px-4 py-5 sm:px-6 sm:py-8 print:max-w-none print:px-0 print:py-0"
        >
          <Outlet />
        </div>
      </main>
    </div>
  )
}
