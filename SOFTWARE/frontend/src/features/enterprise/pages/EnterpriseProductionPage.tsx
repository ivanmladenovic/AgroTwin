import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import {
  compareEnterpriseYieldPlan,
  createEnterpriseSeason,
  createEnterpriseYieldPlan,
  downloadEnterpriseYieldPlanCsv,
  getEnterpriseProductionAnalytics,
  listEnterpriseParcels,
  listEnterpriseSeasons,
  listEnterpriseYieldPlans,
  recalculateEnterpriseYieldPlan,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { EnterpriseOtkupTab } from '@/features/enterprise/pages/EnterpriseOtkupTab'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import { cn } from '@/shared/lib/utils'
import type { EnterpriseParcelSummary, EnterpriseYieldComparison } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
type Tab = 'overview' | 'planning' | 'otkup'

export function EnterpriseProductionPage() {
  useTranslation()
  const { organizationId, canWritePlans } = useEnterprise()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const [tab, setTab] = useState<Tab>(
    tabParam === 'planning' || tabParam === 'otkup' ? tabParam : 'overview',
  )

  useEffect(() => {
    if (tabParam === 'planning' || tabParam === 'otkup') setTab(tabParam)
    else if (tabParam === 'overview' || !tabParam) setTab('overview')
  }, [tabParam])

  function switchTab(next: Tab) {
    setTab(next)
    if (next === 'overview') setSearchParams({}, { replace: true })
    else setSearchParams({ tab: next }, { replace: true })
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="kicker">{tr("Proizvodnja")}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{tr("Proizvodnja i prinos")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr('Analitika berbi, planiranje prinosa i otkup od dobavljača.')}
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <TabButton active={tab === 'overview'} onClick={() => switchTab('overview')}>
          Pregled i analitika
        </TabButton>
        <TabButton active={tab === 'planning'} onClick={() => switchTab('planning')}>
          Planiranje prinosa
        </TabButton>
        <TabButton active={tab === 'otkup'} onClick={() => switchTab('otkup')}>
          Otkup
        </TabButton>
      </div>

      {tab === 'overview' ? (
        <OverviewTab organizationId={organizationId} />
      ) : tab === 'planning' ? (
        <PlanningTab organizationId={organizationId} canWritePlans={canWritePlans} />
      ) : (
        <EnterpriseOtkupTab organizationId={organizationId} canWrite={canWritePlans} />
      )}
    </div>
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

function OverviewTab({ organizationId }: { organizationId: string }) {
  const year = new Date().getFullYear()
  const [selectedParcelIds, setSelectedParcelIds] = useState<Set<string> | null>(null)

  const parcelsQuery = useQuery({
    queryKey: ['enterprise-parcels', organizationId],
    queryFn: () => listEnterpriseParcels(organizationId),
  })

  const allParcels = parcelsQuery.data ?? []

  useEffect(() => {
    if (selectedParcelIds !== null) return
    if (allParcels.length === 0) return
    setSelectedParcelIds(new Set(allParcels.map((p) => p.parcel_id)))
  }, [allParcels, selectedParcelIds])

  const activeParcelIds = useMemo(() => {
    const ids =
      selectedParcelIds === null
        ? allParcels.map((p) => p.parcel_id)
        : [...selectedParcelIds]
    return ids.sort()
  }, [selectedParcelIds, allParcels])

  const analyticsQuery = useQuery({
    queryKey: ['enterprise-production-analytics', organizationId, year, activeParcelIds],
    queryFn: () =>
      getEnterpriseProductionAnalytics(organizationId, {
        year,
        years_back: 6,
        parcel_ids: activeParcelIds,
      }),
    enabled: activeParcelIds.length > 0,
  })

  const analytics = analyticsQuery.data
  const currentYear = analytics?.by_year.find((row) => row.year === year)

  const groups = useMemo(() => groupParcelsBySupplier(allParcels), [allParcels])

  function toggleParcel(parcelId: string) {
    setSelectedParcelIds((prev) => {
      const base = new Set(prev ?? allParcels.map((p) => p.parcel_id))
      if (base.has(parcelId)) base.delete(parcelId)
      else base.add(parcelId)
      return base
    })
  }

  function toggleSupplier(parcelIds: string[], checked: boolean) {
    setSelectedParcelIds((prev) => {
      const base = new Set(prev ?? allParcels.map((p) => p.parcel_id))
      for (const id of parcelIds) {
        if (checked) base.add(id)
        else base.delete(id)
      }
      return base
    })
  }

  function selectAll(checked: boolean) {
    setSelectedParcelIds(
      checked ? new Set(allParcels.map((p) => p.parcel_id)) : new Set(),
    )
  }

  const selectedCount = activeParcelIds.length
  const allSelected = allParcels.length > 0 && selectedCount === allParcels.length

  const visibleParcels = allParcels.filter((p) => activeParcelIds.includes(p.parcel_id))

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-2xl border border-border p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{tr('Obuhvat analitike')}</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {tr('Izaberi dobavljače i parcele. Podrazumevano su sve parcele uključene.')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => selectAll(true)}>
              Sve parcele
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => selectAll(false)}>
              Nijedna
            </Button>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm font-medium">
          <input type="checkbox" checked={allSelected} onChange={(e) => selectAll(e.target.checked)} />
          Sve parcele ({selectedCount}/{allParcels.length})
        </label>

        {parcelsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">{tr('Učitavanje parcela…')}</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {groups.map((group) => {
              const groupSelected = group.parcels.filter((p) =>
                (selectedParcelIds ?? new Set()).has(p.parcel_id),
              ).length
              const groupAll =
                group.parcels.length > 0 && groupSelected === group.parcels.length
              const groupSome = groupSelected > 0 && !groupAll
              return (
                <div key={group.farmId} className="rounded-xl border border-border/80 p-3">
                  <label className="flex items-center gap-2 text-sm font-semibold">
                    <input
                      type="checkbox"
                      checked={groupAll}
                      ref={(el) => {
                        if (el) el.indeterminate = groupSome
                      }}
                      onChange={(e) =>
                        toggleSupplier(
                          group.parcels.map((p) => p.parcel_id),
                          e.target.checked,
                        )
                      }
                    />
                    {group.label}
                    <span className="font-normal text-muted-foreground">
                      ({groupSelected}/{group.parcels.length})
                    </span>
                  </label>
                  <ul className="mt-2 space-y-1.5 pl-6">
                    {group.parcels.map((parcel) => (
                      <li key={parcel.parcel_id}>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={(selectedParcelIds ?? new Set()).has(parcel.parcel_id)}
                            onChange={() => toggleParcel(parcel.parcel_id)}
                          />
                          <span>
                            {parcel.parcel_name}
                            {parcel.default_planting_year != null
                              ? ` · ${parcel.default_planting_year}.`
                              : ''}
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
            {groups.length === 0 ? (
              <p className="text-sm text-muted-foreground">{tr('Nema dodeljenih parcela.')}</p>
            ) : null}
          </div>
        )}
      </section>

      {selectedCount === 0 ? (
        <p className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          {tr('Izaberi bar jednu parcelu da vidiš analitiku.')}
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-primary/20 bg-primary/[0.05] px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {tr('Očekivano bruto ({{year}})', { year })}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {analyticsQuery.isLoading
                  ? '…'
                  : currentYear?.expected_yield_kg != null
                    ? `${formatNumber(currentYear.expected_yield_kg)} kg`
                    : '—'}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{tr('u ljusci, realistični scenario')}</p>
            </div>
            <div className="rounded-2xl border border-border px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {tr('Ostvareno neto')}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {analyticsQuery.isLoading
                  ? '…'
                  : currentYear?.actual_yield_kg != null
                    ? `${formatNumber(currentYear.actual_yield_kg)} kg`
                    : tr('Nije dostupno')}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{tr('berba na nivou parcele')}</p>
            </div>
            <div className="rounded-2xl border border-border px-4 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {tr('Parcele sa berbom')}
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {analyticsQuery.isLoading
                  ? '…'
                  : currentYear
                    ? tr('{{withHarvest}} / {{assigned}}', {
                        withHarvest: formatNumber(currentYear.parcels_with_harvest),
                        assigned: formatNumber(currentYear.assigned_parcels),
                      })
                    : '—'}
              </p>
            </div>
          </div>

          <section className="rounded-2xl border border-border p-4">
            <h2 className="text-sm font-semibold">{tr('Analitika kroz godine')}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {tr(
                'Očekivano (bruto u ljusci) vs ostvareno (neto berba parcele) za {{count}} odabranih parcela. Nedostajuća berba nije prikazana kao nula.',
                { count: selectedCount },
              )}
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-2.5 font-semibold">{tr('Godina')}</th>
                    <th className="px-2 py-2.5 font-semibold">{tr('Očekivano bruto')}</th>
                    <th className="px-2 py-2.5 font-semibold">Ostvareno neto</th>
                    <th className="px-2 py-2.5 font-semibold">{tr('Pokriće parcela')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(analytics?.by_year ?? []).map((row) => (
                    <tr key={row.year} className="border-b border-border/60">
                      <td className="px-2 py-2.5 font-medium">{row.year}</td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {row.expected_yield_kg != null
                          ? `${formatNumber(row.expected_yield_kg)} kg`
                          : '—'}
                      </td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {row.actual_yield_kg != null
                          ? `${formatNumber(row.actual_yield_kg)} kg`
                          : tr('Nije dostupno')}
                      </td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {formatNumber(row.parcels_with_harvest)} /{' '}
                        {formatNumber(row.assigned_parcels)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-border p-4">
            <h2 className="text-sm font-semibold">{tr('Po sortama (ukupno)')}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {tr('Očekivano se računa po sorti iz starosti stabala; ostvareno je proporcionalna procena')}
              {tr('jer berba nije vođena po sorti.')}
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-2.5 font-semibold">Sorta</th>
                    <th className="px-2 py-2.5 font-semibold">{tr("Stabla")}</th>
                    <th className="px-2 py-2.5 font-semibold">Udeo</th>
                    <th className="px-2 py-2.5 font-semibold">{tr('Očekivano bruto')}</th>
                    <th className="px-2 py-2.5 font-semibold">Ostvareno neto</th>
                  </tr>
                </thead>
                <tbody>
                  {(analytics?.by_variety ?? []).map((row) => (
                    <tr key={row.variety} className="border-b border-border/60">
                      <td className="px-2 py-2.5 font-medium">{row.variety}</td>
                      <td className="px-2 py-2.5 tabular-nums">{formatNumber(row.tree_count)}</td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {row.share_of_trees_percent != null
                          ? `${formatNumber(row.share_of_trees_percent)}%`
                          : '—'}
                      </td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {row.expected_yield_kg != null
                          ? `${formatNumber(row.expected_yield_kg)} kg`
                          : '—'}
                      </td>
                      <td className="px-2 py-2.5 tabular-nums">
                        {row.actual_yield_kg != null
                          ? `${formatNumber(row.actual_yield_kg)} kg`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                  {(analytics?.by_variety ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-2 py-6 text-muted-foreground">
                        Nema podataka o sortama.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {(analytics?.notes ?? []).map((note) => (
              <p key={note} className="mt-3 text-xs text-muted-foreground">
                {note}
              </p>
            ))}
          </section>

          <section className="rounded-2xl border border-border p-4">
            <h2 className="text-sm font-semibold">{tr('Odabrane parcele')}</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2.5">{tr("Parcela")}</th>
                    <th className="px-3 py-2.5">{tr("Proizvođač")}</th>
                    <th className="px-3 py-2.5">Sorte</th>
                    <th className="px-3 py-2.5">{tr("Površina")}</th>
                    <th className="px-3 py-2.5">{tr("Očekivano")}</th>
                    <th className="px-3 py-2.5">{tr("Poslednja berba")}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleParcels.map((parcel) => (
                    <tr key={parcel.parcel_id} className="border-b border-border/70">
                      <td className="px-3 py-2.5 font-medium">{parcel.parcel_name}</td>
                      <td className="px-3 py-2.5">
                        {parcel.producer_display_name || parcel.farm_name}
                      </td>
                      <td className="px-3 py-2.5">
                        {(parcel.variety_names ?? []).join(', ') || parcel.default_variety || '—'}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {parcel.area_hectares != null
                          ? `${formatNumber(parcel.area_hectares)} ha`
                          : '—'}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {parcel.expected_yield_kg != null
                          ? `${formatNumber(parcel.expected_yield_kg)} kg`
                          : '—'}
                      </td>
                      <td className="px-3 py-2.5 tabular-nums">
                        {parcel.latest_harvest_kg != null
                          ? `${formatNumber(parcel.latest_harvest_kg)} kg`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function groupParcelsBySupplier(parcels: EnterpriseParcelSummary[]) {
  const map = new Map<
    string,
    { farmId: string; label: string; parcels: EnterpriseParcelSummary[] }
  >()
  for (const parcel of parcels) {
    const key = parcel.farm_id
    const existing = map.get(key)
    if (existing) {
      existing.parcels.push(parcel)
    } else {
      map.set(key, {
        farmId: key,
        label: parcel.producer_display_name || parcel.farm_name,
        parcels: [parcel],
      })
    }
  }
  return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'sr'))
}

function PlanningTab({
  organizationId,
  canWritePlans,
}: {
  organizationId: string
  canWritePlans: boolean
}) {
  const queryClient = useQueryClient()
  const seasonsQuery = useQuery({
    queryKey: ['enterprise-seasons', organizationId],
    queryFn: () => listEnterpriseSeasons(organizationId),
  })
  const [seasonId, setSeasonId] = useState('')
  const [scenario, setScenario] = useState('realistic')
  const [planName, setPlanName] = useState(tr('Realistični scenario'))
  const [compareByPlan, setCompareByPlan] = useState<Record<string, EnterpriseYieldComparison>>({})

  const effectiveSeasonId = seasonId || seasonsQuery.data?.[0]?.id || ''
  const plansQuery = useQuery({
    queryKey: ['enterprise-plans', organizationId, effectiveSeasonId],
    queryFn: () => listEnterpriseYieldPlans(organizationId, effectiveSeasonId || undefined),
    enabled: Boolean(organizationId),
  })

  const createSeason = useMutation({
    mutationFn: () => {
      const year = new Date().getFullYear() + 1
      return createEnterpriseSeason(organizationId, { year, name: `Sezona ${year}` })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-seasons', organizationId] })
    },
  })

  const createPlan = useMutation({
    mutationFn: () =>
      createEnterpriseYieldPlan(organizationId, {
        planning_season_id: effectiveSeasonId,
        name: planName,
        scenario_type: scenario,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-plans', organizationId] })
    },
  })

  const recalculate = useMutation({
    mutationFn: (planId: string) => recalculateEnterpriseYieldPlan(organizationId, planId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-plans', organizationId] })
    },
  })

  async function loadCompare(planId: string) {
    const result = await compareEnterpriseYieldPlan(organizationId, planId)
    setCompareByPlan((prev) => ({ ...prev, [planId]: result }))
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        {tr('Interni scenariji po starosnim kohortama. Ne menjaju berbu proizvođača. Rekalkulacija čuva')}
        stari plan i kreira novu verziju.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">{tr("Sezona")}</label>
          <Select value={effectiveSeasonId} onChange={(e) => setSeasonId(e.target.value)}>
            {(seasonsQuery.data ?? []).map((season) => (
              <option key={season.id} value={season.id}>
                {season.name} ({season.year})
              </option>
            ))}
          </Select>
        </div>
        {canWritePlans ? (
          <Button type="button" variant="outline" onClick={() => createSeason.mutate()} disabled={createSeason.isPending}>
            Nova sezona
          </Button>
        ) : null}
      </div>

      {canWritePlans ? (
        <div className="space-y-3 rounded-2xl border border-border p-4">
          <h2 className="text-sm font-semibold">Novi plan</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input value={planName} onChange={(e) => setPlanName(e.target.value)} placeholder={tr('Naziv plana')} />
            <Select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="conservative">Konzervativni</option>
              <option value="realistic">{tr("Realistični")}</option>
              <option value="optimistic">{tr("Optimistični")}</option>
              <option value="custom">{tr('Prilagođeni')}</option>
            </Select>
            <Button
              type="button"
              onClick={() => createPlan.mutate()}
              disabled={!effectiveSeasonId || createPlan.isPending}
            >
              {tr('Generiši plan')}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="space-y-4">
        {(plansQuery.data ?? []).map((plan) => {
          const comparison = compareByPlan[plan.id]
          return (
            <article key={plan.id} className="rounded-2xl border border-border px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{plan.name}</h3>
                  <p className="text-xs capitalize text-muted-foreground">
                    {plan.scenario_type} · {plan.calculation_version} · {plan.status}
                  </p>
                </div>
                <p className="text-lg font-semibold tabular-nums">
                  {plan.total_forecast_kg != null ? `${formatNumber(plan.total_forecast_kg)} kg` : '—'}
                </p>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => void loadCompare(plan.id)}>
                  Uporedi sa berbom
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void downloadEnterpriseYieldPlanCsv(organizationId, plan.id)}
                >
                  CSV
                </Button>
                {canWritePlans ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => recalculate.mutate(plan.id)}
                    disabled={recalculate.isPending}
                  >
                    {tr('Rekalkuliši (nova verzija)')}
                  </Button>
                ) : null}
              </div>

              {comparison ? (
                <div className="mt-4 space-y-2 rounded-xl border border-border bg-muted/20 p-3">
                  <div className="flex flex-wrap gap-4 text-sm">
                    <span>
                      Prognoza: <strong>{formatNumber(comparison.total_forecast_kg)} kg</strong>
                    </span>
                    <span>
                      Ostvareno:{' '}
                      <strong>
                        {comparison.total_actual_kg != null
                          ? `${formatNumber(comparison.total_actual_kg)} kg`
                          : tr('Nije dostupno')}
                      </strong>
                    </span>
                    <span>
                      Sa berbom: {comparison.parcels_with_harvest} · Bez berbe:{' '}
                      {comparison.parcels_missing_harvest}
                    </span>
                  </div>
                  {comparison.notes.map((note) => (
                    <p key={note} className="text-xs text-muted-foreground">
                      {note}
                    </p>
                  ))}
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left text-sm">
                      <thead className="text-xs uppercase text-muted-foreground">
                        <tr>
                          <th className="py-1 pr-3">{tr("Parcela")}</th>
                          <th className="py-1 pr-3">Prognoza</th>
                          <th className="py-1 pr-3">{tr("Ostvareno")}</th>
                          <th className="py-1 pr-3">Razlika</th>
                          <th className="py-1">%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {comparison.rows.map((row) => (
                          <tr key={row.parcel_id} className="border-t border-border/60">
                            <td className="py-1.5 pr-3">{row.parcel_name ?? row.parcel_id}</td>
                            <td className="py-1.5 pr-3 tabular-nums">
                              {formatNumber(row.forecast_yield_kg)} kg
                            </td>
                            <td className="py-1.5 pr-3 tabular-nums">
                              {row.actual_net_yield_kg != null
                                ? `${formatNumber(row.actual_net_yield_kg)} kg`
                                : '—'}
                            </td>
                            <td className="py-1.5 pr-3 tabular-nums">
                              {row.difference_kg != null ? `${formatNumber(row.difference_kg)} kg` : '—'}
                            </td>
                            <td className="py-1.5 tabular-nums">
                              {row.difference_percent != null
                                ? `${formatNumber(row.difference_percent)}%`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}

              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-1 pr-3">{tr("Parcela")}</th>
                      <th className="py-1 pr-3">{tr("Dobavljač")}</th>
                      <th className="py-1 pr-3">{tr("Stabla")}</th>
                      <th className="py-1">Prognoza</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.items.slice(0, 12).map((item) => (
                      <tr key={item.id} className="border-t border-border/60">
                        <td className="py-1.5 pr-3">{item.parcel_name ?? item.parcel_id}</td>
                        <td className="py-1.5 pr-3">{item.farm_name ?? '—'}</td>
                        <td className="py-1.5 pr-3 tabular-nums">
                          {formatNumber(item.forecast_tree_count ?? 0)}
                        </td>
                        <td className="py-1.5 tabular-nums">{formatNumber(item.forecast_yield_kg)} kg</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {plan.items.length > 12 ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Prikazano 12 od {plan.items.length} stavki.
                  </p>
                ) : null}
              </div>
            </article>
          )
        })}
        {(plansQuery.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">{tr('Još nema sačuvanih planova za izabranu sezonu.')}</p>
        ) : null}
      </div>
    </div>
  )
}
