import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  compareEnterpriseYieldPlan,
  createEnterpriseSeason,
  createEnterpriseYieldPlan,
  downloadEnterpriseYieldPlanCsv,
  listEnterpriseSeasons,
  listEnterpriseYieldPlans,
  recalculateEnterpriseYieldPlan,
} from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import type { EnterpriseYieldComparison } from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
export function EnterprisePlanningPage() {
  useTranslation()
  const { organizationId, canWritePlans } = useEnterprise()
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
      <div>
        <p className="kicker">{tr('Planiranje prinosa')}</p>
        <h1 className="mt-1 text-2xl font-semibold">Enterprise prognoze</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr('Interni scenariji po starosnim kohortama. Ne menjaju berbu proizvođača. Rekalkulacija čuva')}
          stari plan i kreira novu verziju.
        </p>
      </div>

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
        <div className="space-y-3 rounded-xl border border-border p-4">
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
            <article key={plan.id} className="rounded-xl border border-border px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{plan.name}</h3>
                  <p className="text-xs text-muted-foreground capitalize">
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
                <div className="mt-4 space-y-2 rounded-lg border border-border bg-muted/20 p-3">
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
