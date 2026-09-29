import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useParams, useSearchParams } from 'react-router-dom'

import { addActivityCost, deleteSoilAnalysis, downloadSoilAnalysis, getActivity, listCostCategories, openSoilAnalysis, updateActivity } from '@/features/journal/api'
import { activityCalendarKind, activityStatusLabel } from '@/features/journal/labels'
import { todayKey } from '@/features/journal/calendar'
import { costFormSchema, type CostFormValues } from '@/features/journal/schemas'
import type { SoilLabAnalysis } from '@/shared/api/types'
import { activityTarget, formatDate, formatLineItem, formatMoney, formatWorkQuantities, rowLabel, scopeLabel } from '@/shared/lib/format'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function ActivityDetailPage() {
  const { activityId } = useParams()
  const [params] = useSearchParams()
  const returnTo = params.get('returnTo') || '/journal'
  const queryClient = useQueryClient()
  const activityQuery = useQuery({
    queryKey: ['activity', activityId],
    queryFn: () => getActivity(activityId!),
    enabled: Boolean(activityId),
  })
  const categoriesQuery = useQuery({ queryKey: ['cost-categories'], queryFn: listCostCategories })
  const activity = activityQuery.data

  const [addingCost, setAddingCost] = useState(false)
  const form = useForm<CostFormValues>({
    resolver: zodResolver(costFormSchema),
    defaultValues: {
      description: '',
      cost_category_id: '',
      amount: '',
      currency: 'EUR',
      incurred_on: '',
      notes: '',
      receipt_filename: '',
    },
  })

  const mutation = useMutation({
    mutationFn: (values: CostFormValues) =>
      addActivityCost(activityId!, {
        description: values.description,
        cost_category_id: values.cost_category_id,
        amount: Number(values.amount),
        currency: values.currency,
        incurred_on: values.incurred_on || activity?.performed_on || null,
        notes: values.notes || null,
        receipt_filename: values.receipt_filename || null,
      }),
    onSuccess: async () => {
      form.reset({
        description: '',
        cost_category_id: '',
        amount: '',
        currency: 'EUR',
        incurred_on: activity?.performed_on ?? '',
        notes: '',
        receipt_filename: '',
      })
      setAddingCost(false)
      await queryClient.invalidateQueries({ queryKey: ['activity', activityId] })
      await queryClient.invalidateQueries({ queryKey: ['cost-summary'] })
      await queryClient.invalidateQueries({ queryKey: ['costs'] })
    },
  })

  const statusMutation = useMutation({
    mutationFn: (status: 'completed' | 'planned' | 'in_progress') => updateActivity(activityId!, { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['activity', activityId] })
      await queryClient.invalidateQueries({ queryKey: ['activities'] })
    },
  })

  if (activityQuery.isLoading) {
    return <div className="text-sm text-muted-foreground">Učitavanje aktivnosti…</div>
  }
  if (!activity) {
    return <div className="text-sm text-danger">Aktivnost nije pronađena.</div>
  }

  const kind = activityCalendarKind(activity.status, activity.performed_on, todayKey())

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="kicker">
            {activity.activity_type.name}
          </p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{activity.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatDate(activity.performed_on)} · {scopeLabel(activity.scope_type)} · {activityTarget(activity)} ·{' '}
            {kind === 'overdue' ? 'Kasni' : activityStatusLabel(activity.status)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {activity.status !== 'completed' && activity.status !== 'cancelled' ? (
            <Button size="sm" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('completed')}>
              Označi kao urađeno
            </Button>
          ) : null}
          {activity.status === 'completed' ? (
            <Button
              size="sm"
              variant="outline"
              disabled={statusMutation.isPending}
              onClick={() => statusMutation.mutate('planned')}
            >
              Vrati u plan
            </Button>
          ) : null}
          <BackButton fallback={returnTo} />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Stavke troška</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {activity.costs.length === 0 ? (
            <p className="text-sm text-muted-foreground">Još nema stavki. Ova aktivnost trenutno košta 0,00 €.</p>
          ) : (
            <div className="space-y-2">
              {activity.costs.map((cost) => (
                <div key={cost.id} className="flex items-baseline justify-between gap-4 text-sm">
                  <div className="min-w-0">
                    <p>{cost.description}</p>
                    <p className="text-[11px] leading-4 text-muted-foreground">
                      {[cost.cost_category.name, formatWorkQuantities(activity.line_items)].filter(Boolean).join(' · ')}
                    </p>
                  </div>
                  <p className="font-mono">{formatMoney(cost.amount, cost.currency)}</p>
                </div>
              ))}
              <div className="flex items-baseline justify-between border-t border-border pt-3 text-sm font-medium">
                <span>Ukupno</span>
                <span className="font-mono">{formatMoney(activity.total_cost, activity.currency)}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {addingCost ? (
        <Card>
          <CardHeader>
            <CardTitle>Nova stavka troška</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4 md:grid-cols-2"
              onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
            >
              <div className="space-y-1.5">
                <Label>Opis</Label>
                <Input {...form.register('description')} />
              </div>
              <div className="space-y-1.5">
                <Label>Kategorija</Label>
                <Select {...form.register('cost_category_id')}>
                  <option value="">Izaberite kategoriju</option>
                  {(categoriesQuery.data ?? []).map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Iznos</Label>
                <Input type="number" step="0.01" min="0.01" {...form.register('amount')} />
              </div>
              <div className="space-y-1.5">
                <Label>Valuta</Label>
                <Input maxLength={3} {...form.register('currency')} />
              </div>
              <div className="space-y-1.5">
                <Label>Datum</Label>
                <Input type="date" {...form.register('incurred_on')} />
              </div>
              <div className="space-y-1.5">
                <Label>Račun / referenca fotografije</Label>
                <Input {...form.register('receipt_filename')} />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <Label>Beleške</Label>
                <Textarea rows={3} {...form.register('notes')} />
              </div>
              {mutation.isError ? (
                <p className="text-sm text-danger md:col-span-2">
                  {mutation.error instanceof Error ? mutation.error.message : 'Trošak nije dodat'}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-2 md:col-span-2">
                <Button type="submit" disabled={mutation.isPending}>
                  {mutation.isPending ? 'Dodavanje…' : 'Sačuvaj stavku'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={mutation.isPending}
                  onClick={() => {
                    setAddingCost(false)
                    form.reset()
                  }}
                >
                  Otkaži
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : (
        <Button type="button" onClick={() => setAddingCost(true)}>
          + Dodaj stavku troška
        </Button>
      )}

      {activity.soil_analyses?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Analize zemljišta</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {activity.soil_analyses.map((analysis) => (
              <ActivitySoilAnalysisRow
                key={analysis.id}
                analysis={analysis}
                activityId={activity.id}
              />
            ))}
          </CardContent>
        </Card>
      ) : null}

      {activity.description || activity.notes || activity.line_items?.length || activity.quantity ? (
        <Card>
          <CardHeader>
            <CardTitle>Detalji</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {activity.description ? <p>{activity.description}</p> : null}
            {activity.notes ? <p className="text-muted-foreground">{activity.notes}</p> : null}
            {activity.line_items?.length ? (
              <div className="space-y-1">
                {activity.line_items.map((item, index) => (
                  <p key={`${item.unit}-${index}`} className="font-mono text-xs text-muted-foreground">
                    {formatLineItem(item)}
                  </p>
                ))}
              </div>
            ) : activity.quantity ? (
              <p className="font-mono text-xs text-muted-foreground">
                Količina {activity.quantity} {activity.unit ?? ''}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function ActivitySoilAnalysisRow({ analysis, activityId }: { analysis: SoilLabAnalysis; activityId: string }) {
  const queryClient = useQueryClient()
  const [busy, setBusy] = useState<'open' | 'download' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const deleteMutation = useMutation({
    mutationFn: () => deleteSoilAnalysis(analysis.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['activity', activityId] })
      await queryClient.invalidateQueries({ queryKey: ['parcel-soil-analyses', analysis.parcel_id] })
      await queryClient.invalidateQueries({ queryKey: ['activities'] })
    },
  })

  async function handleOpen() {
    setError(null)
    setBusy('open')
    try {
      const opened = await openSoilAnalysis(analysis)
      if (!opened) await downloadSoilAnalysis(analysis)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Otvaranje fajla nije uspelo')
    } finally {
      setBusy(null)
    }
  }

  async function handleDownload() {
    setError(null)
    setBusy('download')
    try {
      await downloadSoilAnalysis(analysis)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preuzimanje nije uspelo')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{analysis.original_filename}</p>
        <p className="text-xs text-muted-foreground">
          {formatDate(analysis.sampled_on)}
          {analysis.row_number != null ? ` · ${rowLabel(analysis.row_number)}` : ''}
          {analysis.tree_public_id ? ` · ${analysis.tree_public_id}` : ''}
        </p>
        {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" disabled={busy !== null || deleteMutation.isPending} onClick={() => void handleOpen()}>
          {busy === 'open' ? 'Otvaranje…' : 'Otvori'}
        </Button>
        <Button type="button" variant="outline" size="sm" disabled={busy !== null || deleteMutation.isPending} onClick={() => void handleDownload()}>
          {busy === 'download' ? 'Preuzimanje…' : 'Preuzmi'}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (!window.confirm(`Obrisati analizu „${analysis.original_filename}”?`)) return
            setError(null)
            deleteMutation.mutate(undefined, {
              onError: (err) => setError(err instanceof Error ? err.message : 'Brisanje nije uspelo'),
            })
          }}
        >
          {deleteMutation.isPending ? 'Brisanje…' : 'Obriši'}
        </Button>
      </div>
    </div>
  )
}
