import { lazy, Suspense, useMemo, type ComponentType } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { FileText, MapPinned, Tractor, Trees } from 'lucide-react'

import { getEnterpriseDashboard, getEnterpriseMapParcels } from '@/features/enterprise/api'
import { EnterpriseDataQualitySection } from '@/features/enterprise/pages/EnterpriseDataQualitySection'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import type { MapParcelItem } from '@/features/dashboard/ParcelsMap'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

import { tr } from '@/shared/i18n/i18n'
const ParcelsMap = lazy(async () => {
  const module = await import('@/features/dashboard/ParcelsMap')
  return { default: module.ParcelsMap }
})

function Kpi({
  label,
  value,
  hint,
  accent,
}: {
  label: string
  value: string
  hint?: string
  accent?: boolean
}) {
  return (
    <div
      className={cn(
        'rounded-2xl border px-4 py-3.5',
        accent
          ? 'border-primary/25 bg-primary/[0.06]'
          : 'border-border/80 bg-card/80',
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function quickActions() {
  return [
    {
      to: 'parcels',
      label: tr('Parcele'),
      description: tr('Pregled dodeljenih zasada'),
      icon: MapPinned,
    },
    {
      to: 'suppliers',
      label: tr('Dobavljači'),
      description: tr('Mreža proizvođača'),
      icon: Tractor,
    },
    {
      to: 'production',
      label: tr('Proizvodnja'),
      description: tr('Analitika i planiranje'),
      icon: Trees,
    },
    {
      to: 'reports',
      label: tr('Izveštaji'),
      description: tr('PDF zbir parcela'),
      icon: FileText,
    },
  ]
}

export function EnterpriseDashboardPage() {
  useTranslation()
  const { organizationId, organization } = useEnterprise()
  const year = new Date().getFullYear()
  const dashQuery = useQuery({
    queryKey: ['enterprise-dashboard', organizationId, year],
    queryFn: () => getEnterpriseDashboard(organizationId, year),
  })
  const mapQuery = useQuery({
    queryKey: ['enterprise-map-parcels', organizationId],
    queryFn: () => getEnterpriseMapParcels(organizationId),
  })
  const data = dashQuery.data
  const base = `/enterprise/${organizationId}`
  const mapParcels = useMemo<MapParcelItem[]>(
    () =>
      (mapQuery.data ?? []).map((parcel) => ({
        id: parcel.parcel_id,
        name: parcel.parcel_name,
        latitude: String(parcel.latitude),
        longitude: String(parcel.longitude),
        tree_count: parcel.tree_count,
        area_hectares: parcel.area_hectares,
        issue_trees: parcel.issue_trees ?? 0,
        monitoring_trees: parcel.monitoring_trees ?? 0,
        open_cases: parcel.open_cases ?? 0,
        subtitle: parcel.producer_display_name,
      })),
    [mapQuery.data],
  )

  return (
    <div className="space-y-8">
      <div>
        <p className="kicker">{tr('Pregled mreže')}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
          {organization?.name ?? 'Enterprise'}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr(
            'Mapa dodeljenih zasada i brzi pristup najvažnijim pregledima. Podaci proizvođača su samo za čitanje.',
          )}
        </p>
      </div>

      {dashQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Priprema pregleda…')}</p>
      ) : data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label={tr("Aktivni dobavljači")} value={formatNumber(data.active_suppliers)} accent />
          <Kpi label={tr('Dodeljene parcele')} value={formatNumber(data.assigned_parcels)} />
          <Kpi
            label={tr("Površina")}
            value={data.total_area_ha != null ? `${formatNumber(data.total_area_ha)} ha` : '—'}
          />
          <Kpi
            label={tr("Stabla")}
            value={data.total_trees != null ? formatNumber(data.total_trees) : '—'}
          />
          <Kpi
            label={tr('Očekivano {{year}}', { year: data.season_year ?? year })}
            value={
              data.expected_yield_kg != null ? `${formatNumber(data.expected_yield_kg)} kg` : '—'
            }
            hint={tr('Procena, nije garancija')}
          />
          <Kpi
            label={tr("Ostvareno")}
            value={
              data.actual_yield_kg != null
                ? `${formatNumber(data.actual_yield_kg)} kg`
                : tr('Nije dostupno')
            }
            hint={tr("Nedostajuća berba nije nula")}
          />
          <Kpi
            label={tr("Pokriće berbe")}
            value={
              data.harvest_coverage_percent != null
                ? `${formatNumber(data.harvest_coverage_percent)}%`
                : '—'
            }
          />
          <Kpi
            label={tr("Nedostajući podaci")}
            value={formatNumber(data.parcels_missing_key_data)}
            hint={tr("Parcele sa ključnim prazninama")}
          />
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-3 xl:items-stretch">
        <section className="flex min-h-[264px] flex-col xl:col-span-2 xl:min-h-[384px]">
          <div className="mb-2 flex items-end justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">{tr('Mapa zasada')}</h2>
              <p className="text-xs text-muted-foreground">{tr('Dodeljeni zasadi sa koordinatama')}</p>
            </div>
          </div>
          <div className="min-h-[264px] flex-1 overflow-hidden rounded-2xl border border-border bg-card sm:min-h-[360px]">
            {mapQuery.isLoading ? (
              <div className="flex h-full min-h-[264px] items-center justify-center sm:min-h-[360px]">
                <p className="text-sm text-muted-foreground">{tr('Učitavanje mape…')}</p>
              </div>
            ) : (
              <Suspense
                fallback={
                  <div className="flex h-full min-h-[264px] items-center justify-center sm:min-h-[360px]">
                    <p className="text-sm text-muted-foreground">{tr('Učitavanje mape…')}</p>
                  </div>
                }
              >
                <ParcelsMap
                  className="h-full min-h-[264px] sm:min-h-[360px]"
                  parcels={mapParcels}
                  getParcelHref={(parcel) => `${base}/parcels/${parcel.id}`}
                  emptyMessage={tr("Nema parcela sa koordinatama za prikaz na mapi.")}
                />
              </Suspense>
            )}
          </div>
        </section>

        <Card className="flex min-h-0 flex-col xl:min-h-[384px]">
          <CardHeader>
            <CardTitle>{tr('Brzi koraci')}</CardTitle>
          </CardHeader>
          <CardContent className="grid flex-1 content-stretch gap-2.5">
            {quickActions().map((action) => (
              <QuickAction
                key={action.to}
                to={`${base}/${action.to}`}
                icon={action.icon}
                label={action.label}
                hint={action.description}
              />
            ))}
          </CardContent>
        </Card>
      </div>

      <EnterpriseDataQualitySection year={year} />

      {data?.notes.length ? (
        <ul className="space-y-1 text-sm text-muted-foreground">
          {data.notes.map((note) => (
            <li key={note}>• {note}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function QuickAction({
  to,
  icon: Icon,
  label,
  hint,
}: {
  to: string
  icon: ComponentType<{ className?: string }>
  label: string
  hint: string
}) {
  return (
    <Link
      to={to}
      className="flex min-h-[3.6rem] flex-1 items-center gap-3 rounded-lg border border-border px-3 py-3 transition-colors hover:bg-muted/70"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
    </Link>
  )
}
