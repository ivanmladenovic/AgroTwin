import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Menu, X } from 'lucide-react'

import { getCurrentUser } from '@/features/auth/api'
import { clearAccessToken } from '@/shared/lib/auth'
import { locationKey } from '@/shared/lib/navigation'
import { Button } from '@/shared/ui/button'
import { BrandLogo } from '@/shared/ui/brand-logo'
import { Separator } from '@/shared/ui/separator'
import { cn } from '@/shared/lib/utils'

const navItems = [
  { to: '/', label: 'Početna', enabled: true, end: true },
  { to: '/orchard', label: 'Zasadi', enabled: true, end: false },
  { to: '/production', label: 'Proizvodnja', enabled: true, end: false },
  { to: '/reports', label: 'Izveštaj', enabled: true, end: false },
  { to: '/journal', label: 'Dnevnik', enabled: true, end: false },
  { to: '/costs', label: 'Troškovi', enabled: true, end: true },
  { to: '/invoices', label: 'Računi', enabled: true, end: false },
  { to: '/health', label: 'Zdravlje stabala', enabled: true, end: false },
  { to: '/agronomist', label: 'Agronom', enabled: true, end: false },
  { to: '/knowledge', label: 'Priručnici', enabled: true, end: false },
]

export function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const userQuery = useQuery({
    queryKey: ['me'],
    queryFn: getCurrentUser,
  })

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', onKey)
    }
  }, [menuOpen])

  function handleSignOut() {
    clearAccessToken()
    void navigate('/login')
  }

  const userName = userQuery.data ? userQuery.data.full_name : 'Učitavanje korisnika…'

  return (
    <div className="flex h-dvh min-h-0 flex-col overflow-hidden print:block print:h-auto print:max-h-none print:overflow-visible lg:flex-row">
      <header className="flex shrink-0 items-center justify-between gap-3 bg-sidebar px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] text-sidebar-foreground print:hidden lg:hidden">
        <NavLink to="/" aria-label="AgroTwin" className="block min-w-0">
          <BrandLogo className="h-[1.6875rem] w-auto max-w-[8.25rem]" />
        </NavLink>
        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-sidebar-foreground hover:bg-white/10"
          aria-label="Otvori meni"
          onClick={() => setMenuOpen(true)}
        >
          <Menu className="h-6 w-6" />
        </button>
      </header>

      <aside className="relative hidden w-64 shrink-0 flex-col overflow-hidden bg-sidebar text-sidebar-foreground print:hidden lg:flex">
        <SidebarDecor />
        <div className="relative z-10 flex justify-center px-5 pb-4 pt-6">
          <NavLink to="/" aria-label="AgroTwin" className="block w-fit">
            <BrandLogo className="w-[8.25rem] max-w-full" />
          </NavLink>
        </div>
        <Separator className="relative z-10 bg-white/10" />
        <SidebarNav />
        <SidebarFooter userName={userName} onSignOut={handleSignOut} />
      </aside>

      {menuOpen ? (
        <div className="fixed inset-0 z-[2000] print:hidden lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Zatvori meni"
            onClick={() => setMenuOpen(false)}
          />
          <aside className="relative flex h-full w-[min(20rem,86vw)] flex-col overflow-hidden bg-sidebar text-sidebar-foreground shadow-xl">
            <SidebarDecor />
            <div className="relative z-10 flex items-center justify-between gap-3 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
              <NavLink to="/" aria-label="AgroTwin" className="block min-w-0">
                <BrandLogo className="h-[1.6875rem] w-auto max-w-[7.5rem]" />
              </NavLink>
              <button
                type="button"
                className="inline-flex h-11 w-11 items-center justify-center rounded-lg hover:bg-white/10"
                aria-label="Zatvori meni"
                onClick={() => setMenuOpen(false)}
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <Separator className="relative z-10 bg-white/10" />
            <SidebarNav />
            <SidebarFooter userName={userName} onSignOut={handleSignOut} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col print:block print:h-auto print:max-h-none print:min-h-0 print:overflow-visible">
        <main
          data-app-scroll="main"
          className="flex min-h-0 flex-1 flex-col overflow-auto overflow-x-clip p-4 pb-[max(1rem,env(safe-area-inset-bottom))] print:block print:h-auto print:max-h-none print:overflow-visible print:p-0 lg:p-6"
        >
          <ScrollMemory />
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function ScrollMemory() {
  const location = useLocation()

  useEffect(() => {
    const main = document.querySelector<HTMLElement>('[data-app-scroll="main"]')
    if (!main) return

    const key = `agrotwin:scroll:${locationKey(location.pathname, location.search)}`
    const saved = sessionStorage.getItem(key)
    const target = saved != null ? Number(saved) : 0
    let cancelled = false

    function restore() {
      if (cancelled || Number.isNaN(target)) return
      main.scrollTop = target
    }

    restore()
    const frame = requestAnimationFrame(restore)
    const timers = [50, 150, 400, 800].map((ms) => window.setTimeout(restore, ms))

    function persist() {
      sessionStorage.setItem(key, String(main.scrollTop))
    }

    main.addEventListener('scroll', persist, { passive: true })
    return () => {
      cancelled = true
      persist()
      cancelAnimationFrame(frame)
      timers.forEach((id) => window.clearTimeout(id))
      main.removeEventListener('scroll', persist)
    }
  }, [location.pathname, location.search])

  return null
}

function SidebarDecor() {
  return (
    <div
      className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_22%_10%,rgba(90,173,69,0.28),transparent_38%),radial-gradient(circle_at_85%_88%,rgba(46,179,190,0.14),transparent_42%)]"
      aria-hidden
    />
  )
}

function SidebarNav() {
  const location = useLocation()
  return (
    <nav className="relative z-10 flex flex-1 flex-col gap-1 overflow-auto px-3 py-4">
      {navItems.map((item) =>
        item.enabled ? (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) => {
              const active =
                isActive ||
                (item.to === '/reports' && location.pathname.includes('/report')) ||
                (item.to === '/production' && location.pathname.includes('/production'))
              return cn(
                'rounded-lg px-3 py-3 text-sm font-medium transition-colors lg:py-2',
                active
                  ? 'bg-accent/20 text-white shadow-[inset_3px_0_0_0_var(--color-accent)]'
                  : 'text-sidebar-foreground/75 hover:bg-white/5 hover:text-white',
              )
            }}
          >
            {item.label}
          </NavLink>
        ) : (
          <span
            key={item.to}
            className="flex items-center justify-between rounded-lg px-3 py-3 text-sm text-sidebar-foreground/35 lg:py-2"
          >
            {item.label}
            <span className="kicker text-[10px] tracking-wider">Kasnije</span>
          </span>
        ),
      )}
    </nav>
  )
}

function SidebarFooter({ userName, onSignOut }: { userName: string; onSignOut: () => void }) {
  return (
    <div className="relative z-10 mt-auto space-y-3 px-3 pb-[max(1rem,env(safe-area-inset-bottom))] pt-2 lg:pb-4">
      <p className="px-2 text-xs text-sidebar-foreground/50">{userName}</p>
      <Button
        variant="outline"
        size="sm"
        className="h-11 w-full border-white/15 bg-white/5 text-sidebar-foreground hover:bg-white/10 hover:text-white lg:h-8"
        onClick={onSignOut}
      >
        Odjava
      </Button>
    </div>
  )
}
