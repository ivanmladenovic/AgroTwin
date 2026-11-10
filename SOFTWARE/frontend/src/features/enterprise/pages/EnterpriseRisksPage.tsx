import { useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import {
  getEnterpriseAlertWatch,
  getEnterpriseMonitoring,
  type EnterpriseMonitoringParams,
} from '@/features/enterprise/api'
import { EnterpriseAlertWatchSection } from '@/features/enterprise/pages/EnterpriseAlertWatchSection'
import { EnterpriseFollowUpsSection } from '@/features/enterprise/pages/EnterpriseFollowUpsSection'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatNumber } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import type {
  EnterpriseAttentionItem,
  EnterpriseDataQualityItem,
  EnterpriseMetricAvailability,
  EnterpriseMonitoringActivityItem,
  EnterpriseMonitoringObservationItem,
  EnterpriseMonitoringPlanItem,
} from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
type PageTab = 'alerts' | 'field' | 'tasks'
type FocusSection = 'attention' | 'observations' | 'activities' | 'plans' | 'quality'

export function EnterpriseRisksPage() {
  useTranslation()
  const { organizationId } = useEnterprise()
  const [searchParams, setSearchParams] = useSearchParams()
  const yearNow = new Date().getFullYear()

  const tabParam = searchParams.get('tab')
  const tab: PageTab = tabParam === 'field' ? 'field' : tabParam === 'tasks' ? 'tasks' : 'alerts'

  const filters = useMemo(() => parseFilters(searchParams, yearNow), [searchParams, yearNow])
  const focus = (searchParams.get('focus') as FocusSection | null) || 'attention'
  const [selectedItem, setSelectedItem] = useState<EnterpriseAttentionItem | null>(null)
  const [showMoreFilters, setShowMoreFilters] = useState(hasExtraFieldFilters(filters))

  const monitoringQuery = useQuery({
    queryKey: ['enterprise-monitoring', organizationId, filters],
    queryFn: () => getEnterpriseMonitoring(organizationId, filters),
    enabled: tab === 'field',
  })

  const alertCountQuery = useQuery({
    queryKey: ['enterprise-alert-watch', organizationId, 'tab-badge'],
    queryFn: () => getEnterpriseAlertWatch(organizationId, { limit: 1, offset: 0 }),
    enabled: tab === 'alerts' || tab === 'field',
  })

  // Prefetch filter meta for alerts tab (suppliers/parcels) from monitoring endpoint once.
  const filterMetaQuery = useQuery({
    queryKey: ['enterprise-monitoring', organizationId, 'filter-meta', yearNow],
    queryFn: () => getEnterpriseMonitoring(organizationId, { year: yearNow }),
    enabled: tab === 'alerts',
    staleTime: 60_000,
  })

  const data = monitoringQuery.data
  const filterMeta = tab === 'alerts' ? filterMetaQuery.data : data
  const labels = data?.category_labels ?? {}
  const attentionItems = useMemo(
    () => (data?.attention_items ?? []).filter((item) => item.category !== 'weather_forecast'),
    [data?.attention_items],
  )
  const categoryOptions = useMemo(
    () => (data?.filters.categories ?? []).filter((c) => c !== 'weather_forecast'),
    [data?.filters.categories],
  )

  function switchTab(next: PageTab) {
    const params = new URLSearchParams(searchParams)
    if (next === 'alerts') params.delete('tab')
    else params.set('tab', next)
    setSearchParams(params, { replace: true })
  }

  function setFilterField(key: keyof EnterpriseMonitoringParams, value: string) {
    const next = new URLSearchParams(searchParams)
    if (!value) next.delete(key)
    else next.set(key, value)
    setSearchParams(next, { replace: true })
  }

  function clearFilters() {
    const next = new URLSearchParams()
    for (const [key, value] of searchParams.entries()) {
      if (key.startsWith('alert_') || key === 'tab') next.append(key, value)
    }
    setSearchParams(next, { replace: true })
    setShowMoreFilters(false)
  }

  function setFocus(section: FocusSection) {
    const next = new URLSearchParams(searchParams)
    next.set('focus', section)
    if (section !== 'attention') next.delete('category')
    setSearchParams(next, { replace: true })
  }

  const parcelsForFarm = useMemo(() => {
    const all = filterMeta?.filters.parcels ?? []
    if (!filters.farm_id) return all
    return all.filter((p) => p.farm_id === filters.farm_id)
  }, [filterMeta?.filters.parcels, filters.farm_id])

  const openAlerts = alertCountQuery.data?.open_alerts

  return (
    <div className="space-y-6">
      <div>
        <p className="kicker">{tr('Aktivnosti i rizici')}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{tr('Aktivnosti i rizici')}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Satelitska upozorenja i terenski pregled dodeljenih parcela.
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <TabButton active={tab === 'alerts'} onClick={() => switchTab('alerts')}>
          Upozorenja
          {openAlerts != null ? (
            <span className="ml-1.5 tabular-nums text-muted-foreground">({formatNumber(openAlerts)})</span>
          ) : null}
        </TabButton>
        <TabButton active={tab === 'field'} onClick={() => switchTab('field')}>
          Terenski rad
        </TabButton>
        <TabButton active={tab === 'tasks'} onClick={() => switchTab('tasks')}>
          Zadaci
        </TabButton>
      </div>

      {tab === 'tasks' ? (
        <EnterpriseFollowUpsSection />
      ) : tab === 'alerts' ? (
        <EnterpriseAlertWatchSection
          suppliers={filterMeta?.filters.suppliers ?? []}
          parcels={filterMeta?.filters.parcels ?? []}
        />
      ) : (
        <div className="space-y-5">
          <div className="space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <Field label={tr("Sezona")} className="w-28">
                <Input
                  type="number"
                  value={filters.year ?? yearNow}
                  onChange={(e) => setFilterField('year', e.target.value)}
                />
              </Field>
              <Field label={tr("Dobavljač")} className="min-w-[10rem] flex-1">
                <Select
                  value={filters.farm_id ?? ''}
                  onChange={(e) => {
                    const next = new URLSearchParams(searchParams)
                    if (!e.target.value) next.delete('farm_id')
                    else next.set('farm_id', e.target.value)
                    next.delete('parcel_id')
                    setSearchParams(next, { replace: true })
                  }}
                >
                  <option value="">{tr('Svi dobavljači')}</option>
                  {(data?.filters.suppliers ?? []).map((s) => (
                    <option key={s.farm_id} value={s.farm_id}>
                      {s.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={tr("Parcela")} className="min-w-[10rem] flex-1">
                <Select
                  value={filters.parcel_id ?? ''}
                  onChange={(e) => setFilterField('parcel_id', e.target.value)}
                >
                  <option value="">{tr('Sve parcele')}</option>
                  {parcelsForFarm.map((p) => (
                    <option key={p.parcel_id} value={p.parcel_id}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="flex flex-wrap gap-2 pb-0.5">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowMoreFilters((v) => !v)}
                >
                  {showMoreFilters ? tr('Manje filtera') : tr('Više filtera')}
                </Button>
                {hasAnyFieldFilter(filters, yearNow) ? (
                  <Button type="button" variant="outline" size="sm" onClick={clearFilters}>
                    {tr('Obriši')}
                  </Button>
                ) : null}
              </div>
            </div>

            {showMoreFilters ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Kategorija">
                  <Select
                    value={filters.category ?? ''}
                    onChange={(e) => setFilterField('category', e.target.value)}
                  >
                    <option value="">{tr('Sve kategorije')}</option>
                    {categoryOptions.map((c) => (
                      <option key={c} value={c}>
                        {labels[c] ?? c}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Status pregleda">
                  <Select
                    value={filters.review_status ?? ''}
                    onChange={(e) => setFilterField('review_status', e.target.value)}
                  >
                    <option value="">{tr('Svi statusi')}</option>
                    {(data?.filters.review_statuses ?? []).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={tr("Težina")}>
                  <Select
                    value={filters.severity ?? ''}
                    onChange={(e) => setFilterField('severity', e.target.value)}
                  >
                    <option value="">{tr('Sve težine')}</option>
                    {(data?.filters.severities ?? []).map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Datum od">
                  <Input
                    type="date"
                    value={filters.date_from ?? ''}
                    onChange={(e) => setFilterField('date_from', e.target.value)}
                  />
                </Field>
                <Field label="Datum do">
                  <Input
                    type="date"
                    value={filters.date_to ?? ''}
                    onChange={(e) => setFilterField('date_to', e.target.value)}
                  />
                </Field>
              </div>
            ) : null}

            <p className="text-xs text-muted-foreground">
              Period {data?.period_from ?? '—'} — {data?.period_to ?? '—'}. Samo dodeljene parcele.
            </p>
          </div>

          {(data?.notes ?? []).map((note) => (
            <p
              key={note}
              className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm"
            >
              {note}
            </p>
          ))}

          <div className="flex flex-wrap gap-1.5">
            <FocusChip
              label={tr("Zahteva pažnju")}
              metric={data?.kpis.parcels_for_review}
              active={focus === 'attention'}
              onClick={() => {
                const next = new URLSearchParams(searchParams)
                next.set('focus', 'attention')
                next.delete('category')
                setSearchParams(next, { replace: true })
              }}
            />
            <FocusChip
              label="Problemi"
              metric={data?.kpis.open_problems}
              active={focus === 'attention' && filters.category === 'reported_problem'}
              onClick={() => {
                const next = new URLSearchParams(searchParams)
                next.set('focus', 'attention')
                next.set('category', 'reported_problem')
                setSearchParams(next, { replace: true })
              }}
            />
            <FocusChip
              label={tr("Zapažanja")}
              metric={data?.kpis.new_observations}
              active={focus === 'observations'}
              onClick={() => setFocus('observations')}
            />
            <FocusChip
              label={tr("Aktivnosti")}
              metric={undefined}
              count={data?.activities.length}
              active={focus === 'activities'}
              onClick={() => setFocus('activities')}
            />
            <FocusChip
              label="Planovi"
              metric={data?.kpis.pending_plan_tasks}
              active={focus === 'plans'}
              onClick={() => setFocus('plans')}
            />
            <FocusChip
              label="Podaci"
              metric={data?.kpis.incomplete_data}
              active={focus === 'quality'}
              onClick={() => {
                const next = new URLSearchParams(searchParams)
                next.set('focus', 'quality')
                next.set('category', 'incomplete_data')
                setSearchParams(next, { replace: true })
              }}
            />
          </div>

          {data?.kpis.stale_data.available && (data.kpis.stale_data.value ?? 0) > 0 ? (
            <button
              type="button"
              onClick={() => {
                const next = new URLSearchParams(searchParams)
                next.set('focus', 'quality')
                next.set('category', 'stale_data')
                setSearchParams(next, { replace: true })
              }}
              className="text-left text-xs text-muted-foreground underline-offset-2 hover:underline"
            >
              Zastareli podaci (lab): {formatNumber(data.kpis.stale_data.value ?? 0)}
              {data.kpis.stale_data.note ? ` — ${data.kpis.stale_data.note}` : ''}
            </button>
          ) : null}

          {monitoringQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
          ) : null}

          {focus === 'attention' ? (
            <Section title={tr("Zahteva pažnju")} hint="Prioritetne stavke za izabrani period.">
              <AttentionList
                organizationId={organizationId}
                items={attentionItems}
                onSelect={setSelectedItem}
                empty={tr("Nema stavki koje zahtevaju pažnju za izabrani period i filtere.")}
              />
            </Section>
          ) : null}

          {focus === 'observations' ? (
            <Section title={tr("Zapažanja")} hint={tr("Samo čitanje — Enterprise ne menja proizvođačke zapise.")}>
              <ObservationList
                organizationId={organizationId}
                items={data?.observations ?? []}
                empty={tr("Nema zapažanja u izabranom periodu.")}
              />
            </Section>
          ) : null}

          {focus === 'activities' ? (
            <Section title={tr("Aktivnosti")} hint={tr('Evidentirane terenske aktivnosti na parcelama.')}>
              <ActivityList
                organizationId={organizationId}
                items={data?.activities ?? []}
                empty={tr("Nema evidentiranih aktivnosti u izabranom periodu.")}
              />
            </Section>
          ) : null}

          {focus === 'plans' ? (
            <Section title={tr('Planirane stavke')} hint={tr("Stavke iz planova zaštite, ishrane i navodnjavanja.")}>
              <PlanList
                organizationId={organizationId}
                items={data?.plan_items ?? []}
                empty={tr("Nema planiranih stavki za izabranu sezonu.")}
              />
            </Section>
          ) : null}

          {focus === 'quality' ? (
            <Section title={tr('Kvalitet podataka')} hint="Nepotpuna polja i zastarela lab analiza.">
              <QualityList
                organizationId={organizationId}
                items={data?.data_quality ?? []}
                staleNote={data?.kpis.stale_data.note}
                empty={tr("Nema upozorenja o kvalitetu podataka.")}
              />
            </Section>
          ) : null}

          {selectedItem ? (
            <DetailDrawer
              item={selectedItem}
              organizationId={organizationId}
              onClose={() => setSelectedItem(null)}
            />
          ) : null}
        </div>
      )}
    </div>
  )
}

function parseFilters(
  params: URLSearchParams,
  yearNow: number,
): EnterpriseMonitoringParams {
  const yearRaw = params.get('year')
  const year = yearRaw ? Number(yearRaw) : yearNow
  return {
    year: Number.isFinite(year) ? year : yearNow,
    farm_id: params.get('farm_id') || undefined,
    parcel_id: params.get('parcel_id') || undefined,
    category: params.get('category') || undefined,
    review_status: params.get('review_status') || undefined,
    severity: params.get('severity') || undefined,
    date_from: params.get('date_from') || undefined,
    date_to: params.get('date_to') || undefined,
  }
}

function hasExtraFieldFilters(filters: EnterpriseMonitoringParams) {
  return Boolean(
    filters.category ||
      filters.review_status ||
      filters.severity ||
      filters.date_from ||
      filters.date_to,
  )
}

function hasAnyFieldFilter(filters: EnterpriseMonitoringParams, yearNow: number) {
  return Boolean(
    (filters.year != null && filters.year !== yearNow) ||
      filters.farm_id ||
      filters.parcel_id ||
      hasExtraFieldFilters(filters),
  )
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
        active
          ? 'border-primary bg-primary/10 text-foreground'
          : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={cn('block space-y-1 text-xs text-muted-foreground', className)}>
      <span>{label}</span>
      {children}
    </label>
  )
}

function FocusChip({
  label,
  metric,
  count,
  active,
  onClick,
}: {
  label: string
  metric?: EnterpriseMetricAvailability
  count?: number
  active?: boolean
  onClick: () => void
}) {
  const unavailable = metric && !metric.available
  const value =
    count != null
      ? formatNumber(count)
      : unavailable
        ? 'N/D'
        : metric?.value != null
          ? formatNumber(metric.value)
          : metric
            ? '—'
            : '…'

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors',
        active
          ? 'border-primary bg-primary/10 font-medium text-foreground'
          : 'border-border text-muted-foreground hover:bg-muted/40 hover:text-foreground',
      )}
    >
      <span>{label}</span>
      <span className="tabular-nums text-foreground">{value}</span>
    </button>
  )
}

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
      </div>
      {children}
    </section>
  )
}

function AttentionList({
  organizationId,
  items,
  onSelect,
  empty,
}: {
  organizationId: string
  items: EnterpriseAttentionItem[]
  onSelect: (item: EnterpriseAttentionItem) => void
  empty: string
}) {
  if (items.length === 0) {
    return <p className="px-4 py-8 text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li key={item.id} className="px-4 py-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium">
                  {item.category_label}
                </span>
                {item.severity ? (
                  <span className="text-[11px] uppercase text-muted-foreground">{item.severity}</span>
                ) : null}
              </div>
              <button
                type="button"
                className="text-left text-sm font-semibold hover:underline"
                onClick={() => onSelect(item)}
              >
                {item.title}
              </button>
              <p className="text-xs text-muted-foreground">
                {item.producer_display_name || item.farm_name} · {item.parcel_name}
                {item.event_date ? ` · ${item.event_date}` : ''}
              </p>
              <p className="text-xs text-muted-foreground">{item.reason}</p>
            </div>
            <Link
              className="text-xs font-medium text-primary hover:underline"
              to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
            >
              Parcela
            </Link>
          </div>
        </li>
      ))}
    </ul>
  )
}

function ObservationList({
  organizationId,
  items,
  empty,
}: {
  organizationId: string
  items: EnterpriseMonitoringObservationItem[]
  empty: string
}) {
  if (items.length === 0) {
    return <p className="px-4 py-8 text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li
          key={`${item.semantic_type}-${item.id}`}
          className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
        >
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium">{item.title}</p>
            <p className="text-xs text-muted-foreground">
              {item.producer_display_name || item.farm_name} · {item.parcel_name} · {item.performed_on}
            </p>
            <p className="text-xs text-muted-foreground">
              {[item.observation_category, item.observation_status, item.observation_severity, item.source]
                .filter(Boolean)
                .join(' · ')}
            </p>
            {item.description ? (
              <p className="line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
            ) : null}
          </div>
          <Link
            className="text-xs font-medium text-primary hover:underline"
            to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
          >
            Parcela
          </Link>
        </li>
      ))}
    </ul>
  )
}

function ActivityList({
  organizationId,
  items,
  empty,
}: {
  organizationId: string
  items: EnterpriseMonitoringActivityItem[]
  empty: string
}) {
  if (items.length === 0) {
    return <p className="px-4 py-8 text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium">{item.title}</p>
            <p className="text-xs text-muted-foreground">
              {item.producer_display_name || item.farm_name} · {item.parcel_name} · {item.performed_on}
            </p>
            <p className="text-xs text-muted-foreground">
              {[item.activity_type_name, item.semantic_type, item.status].filter(Boolean).join(' · ')}
            </p>
          </div>
          <Link
            className="text-xs font-medium text-primary hover:underline"
            to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
          >
            Parcela
          </Link>
        </li>
      ))}
    </ul>
  )
}

function PlanList({
  organizationId,
  items,
  empty,
}: {
  organizationId: string
  items: EnterpriseMonitoringPlanItem[]
  empty: string
}) {
  if (items.length === 0) {
    return <p className="px-4 py-8 text-sm text-muted-foreground">{empty}</p>
  }
  const order = ['overdue', 'due_soon', 'planned', 'completed', 'cancelled']
  const sorted = [...items].sort((a, b) => order.indexOf(a.bucket) - order.indexOf(b.bucket))
  return (
    <ul className="divide-y divide-border">
      {sorted.map((item) => (
        <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium">
                {planBucketLabel(item.bucket)}
              </span>
              <span className="text-[11px] text-muted-foreground">{item.status}</span>
            </div>
            <p className="text-sm font-medium">{item.title}</p>
            <p className="text-xs text-muted-foreground">
              {item.producer_display_name || item.farm_name} · {item.parcel_name}
            </p>
            <p className="text-xs text-muted-foreground">
              {item.planned_date_from ?? '—'} → {item.planned_date_to ?? '—'}
              {item.item_kind ? ` · ${item.item_kind}` : ''}
            </p>
          </div>
          <Link
            className="text-xs font-medium text-primary hover:underline"
            to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
          >
            Parcela
          </Link>
        </li>
      ))}
    </ul>
  )
}

function planBucketLabel(bucket: string) {
  switch (bucket) {
    case 'overdue':
      return 'Zakasnelo'
    case 'due_soon':
      return 'Uskoro'
    case 'completed':
      return tr('Završeno')
    case 'cancelled':
      return tr('Otkazano')
    default:
      return tr('Planirano')
  }
}

function QualityList({
  organizationId,
  items,
  staleNote,
  empty,
}: {
  organizationId: string
  items: EnterpriseDataQualityItem[]
  staleNote?: string | null
  empty: string
}) {
  if (items.length === 0) {
    return <p className="px-4 py-8 text-sm text-muted-foreground">{empty}</p>
  }
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li
          key={`${item.kind}-${item.parcel_id}`}
          className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
        >
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium">
              {item.kind === 'stale_soil_lab' ? 'Zastarela lab analiza' : 'Nepotpuni podaci'}
              {' · '}
              {item.parcel_name}
            </p>
            <p className="text-xs text-muted-foreground">
              {item.producer_display_name || item.farm_name}
              {item.completeness_score != null
                ? ` · completeness ${formatNumber(item.completeness_score)}%`
                : ''}
            </p>
            <p className="text-xs text-muted-foreground">{item.detail}</p>
            {item.kind === 'stale_soil_lab' && staleNote ? (
              <p className="text-[11px] text-muted-foreground">{staleNote}</p>
            ) : null}
          </div>
          <Link
            className="text-xs font-medium text-primary hover:underline"
            to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
          >
            Parcela
          </Link>
        </li>
      ))}
    </ul>
  )
}

function DetailDrawer({
  item,
  organizationId,
  onClose,
}: {
  item: EnterpriseAttentionItem
  organizationId: string
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/30" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-md flex-col border-l border-border bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{item.category_label}</p>
            <h3 className="mt-1 text-base font-semibold">{item.title}</h3>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Zatvori
          </Button>
        </div>
        <div className="space-y-3 overflow-y-auto px-4 py-4 text-sm">
          <Row label={tr("Dobavljač")} value={item.producer_display_name || item.farm_name} />
          <Row label={tr("Parcela")} value={item.parcel_name} />
          <Row label="Datum" value={item.event_date ?? '—'} />
          <Row label="Izvor" value={`${item.source} · ${item.source_type}`} />
          <Row label="Status" value={item.review_status ?? '—'} />
          <Row label={tr("Težina")} value={item.severity ?? '—'} />
          <div>
            <p className="text-xs text-muted-foreground">Opis</p>
            <p className="mt-1">{item.description || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{tr('Zašto je na listi')}</p>
            <p className="mt-1">{item.reason}</p>
          </div>
          <p className="rounded-xl border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            {tr('Enterprise pristup je samo za čitanje. Ne možete menjati proizvođačke zapise.')}
          </p>
          <Link
            className="inline-flex text-sm font-medium text-primary hover:underline"
            to={`/enterprise/${organizationId}/parcels/${item.parcel_id}`}
          >
            Otvori parcelu
          </Link>
        </div>
      </aside>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-medium">{value}</p>
    </div>
  )
}
