import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { listActivityTypes, createActivity } from '@/features/journal/api'
import { listParcelRows, listParcelTrees, listParcels } from '@/features/orchard/api'
import {
  createPlanningPlan,
  createPlanningPlanItem,
  createPlanningSeason,
  finishPlanningSeason,
  getPlanningPlan,
  getPlanningSummary,
  listPlanningPlans,
  updatePlanningPlanItem,
  updatePlanningSeason,
} from '@/features/planning/api'
import { PLAN_TYPE_LABELS, itemStatusLabel, seasonStatusLabel } from '@/features/planning/labels'
import { formatDate } from '@/shared/lib/format'
import type {
  PlanningParcelSummary,
  PlanningPlan,
  PlanningPlanItem,
  PlanningPlanType,
  PlanningSeason,
} from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

import { tr } from '@/shared/i18n/i18n'
const PLAN_PATH: Record<PlanningPlanType, string> = {
  protection: 'protection',
  nutrition: 'nutrition',
  irrigation: 'irrigation',
}

const CATEGORY_ITEM_KIND: Record<PlanningPlanType, string> = {
  protection: 'assessment',
  nutrition: 'fertilization_window',
  irrigation: 'irrigation_window',
}

const ACTIVITY_TYPE_SLUG: Record<PlanningPlanType, string[]> = {
  protection: ['spraying', 'plant_protection', 'treatment', 'inspection'],
  nutrition: ['fertilization', 'fertilizing'],
  irrigation: ['irrigation'],
}

type ProductLine = { name: string; quantity: string; unit: string }

export function PlanningPage() {
  const { section } = useParams()
  const [params, setParams] = useSearchParams()
  const queryClient = useQueryClient()
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const parcels = parcelsQuery.data ?? []
  const selectedParcelId = params.get('parcelId') || parcels[0]?.id || ''
  const requestedYear = Number(params.get('year') || '')
  const currentYear = new Date().getFullYear()
  const year = Number.isInteger(requestedYear) && requestedYear >= 1990 ? requestedYear : currentYear

  const summaryQuery = useQuery({
    queryKey: ['planning-summary', selectedParcelId],
    queryFn: () => getPlanningSummary(selectedParcelId),
    enabled: Boolean(selectedParcelId),
  })
  const summary = summaryQuery.data
  const seasons = summary?.seasons ?? []
  const selectedSeason = useMemo(
    () => seasons.find((item) => item.year === year) ?? null,
    [seasons, year],
  )

  const [createError, setCreateError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [calendarMessage, setCalendarMessage] = useState<string | null>(null)

  const createMutation = useMutation({
    mutationFn: () => createPlanningSeason(selectedParcelId, { year }),
    onSuccess: async (season) => {
      setCreateError(null)
      await queryClient.invalidateQueries({ queryKey: ['planning-summary', selectedParcelId] })
      const next = new URLSearchParams(params)
      next.set('year', String(season.year))
      setParams(next, { replace: true })
    },
    onError: (error) => {
      setCreateError(error instanceof Error ? error.message : tr('Kreiranje godišnjeg plana nije uspelo'))
    },
  })

  const finishMutation = useMutation({
    mutationFn: (seasonId: string) => finishPlanningSeason(seasonId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['planning-summary', selectedParcelId] })
    },
  })

  const saveMutation = useMutation({
    mutationFn: async (seasonId: string) => updatePlanningSeason(seasonId, { status: 'active' }),
    onSuccess: async () => {
      setSaveMessage(tr('Godišnji plan je sačuvan.'))
      await queryClient.invalidateQueries({ queryKey: ['planning-summary', selectedParcelId] })
    },
    onError: (error) => {
      setSaveMessage(error instanceof Error ? error.message : tr('Čuvanje nije uspelo'))
    },
  })

  if (section && !['protection', 'nutrition', 'irrigation'].includes(section)) {
    return <Navigate to="/journal/planning" replace />
  }

  if (!selectedParcelId && !parcelsQuery.isLoading) {
    return <p className="text-sm text-muted-foreground">{tr('Nema parcele za planiranje. Prvo napravite zasad.')}</p>
  }

  function updateParcel(nextParcelId: string) {
    const next = new URLSearchParams(params)
    next.set('parcelId', nextParcelId)
    next.set('year', String(year))
    setParams(next, { replace: true })
  }

  function updateYear(nextYear: number) {
    const next = new URLSearchParams(params)
    next.set('year', String(nextYear))
    setParams(next, { replace: true })
  }

  const yearOptions = useMemo(() => {
    const values = new Set<number>([currentYear - 1, currentYear, currentYear + 1, year])
    for (const season of seasons) values.add(season.year)
    return [...values].sort((a, b) => a - b)
  }, [currentYear, seasons, year])

  const activeFilter = section
    ? (Object.entries(PLAN_PATH).find(([, path]) => path === section)?.[0] as PlanningPlanType | undefined)
    : undefined

  return (
    <div className="w-full space-y-6 pb-20 sm:pb-0">
      <div>
        <p className="kicker">{tr('Planiranje')}</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{tr('Planiranje')}</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {tr('Godišnji plan zaštite, ishrane i navodnjavanja.')}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1.5">
          <Label>{tr('Parcela')}</Label>
          <Select value={selectedParcelId} onChange={(event) => updateParcel(event.target.value)}>
            {parcels.map((parcel) => (
              <option key={parcel.id} value={parcel.id}>
                {parcel.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Sezona</Label>
          <Select value={String(year)} onChange={(event) => updateYear(Number(event.target.value))}>
            {yearOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <NavChip to={`/journal/planning?parcelId=${selectedParcelId}&year=${year}`} active={!section}>
          Pregled
        </NavChip>
        <NavChip
          to={`/journal/planning/protection?parcelId=${selectedParcelId}&year=${year}`}
          active={section === 'protection'}
        >
          {tr('Zaštita')}
        </NavChip>
        <NavChip
          to={`/journal/planning/nutrition?parcelId=${selectedParcelId}&year=${year}`}
          active={section === 'nutrition'}
        >
          Ishrana
        </NavChip>
        <NavChip
          to={`/journal/planning/irrigation?parcelId=${selectedParcelId}&year=${year}`}
          active={section === 'irrigation'}
        >
          Navodnjavanje
        </NavChip>
      </div>

      {summaryQuery.isLoading ? <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p> : null}
      {summaryQuery.isError ? <p className="text-sm text-danger">{tr('Sažetak parcele nije učitan.')}</p> : null}
      {summary ? (
        <ParcelSummaryCard
          summary={summary}
          editHref={`/orchard/${summary.parcel_id}/edit?returnTo=${encodeURIComponent(
            `/journal/planning${section ? `/${section}` : ''}?parcelId=${summary.parcel_id}&year=${year}`,
          )}`}
        />
      ) : null}

      <section className="space-y-4 rounded-xl border border-border/70 bg-background/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">{tr('Godišnji plan — {{year}}', { year })}</h2>
            <p className="text-xs text-muted-foreground">
              {selectedSeason
                ? `Status: ${seasonStatusLabel(selectedSeason.status)}`
                : tr('Još nema godišnjeg plana za ovu sezonu. Kreirajte ga da biste dodavali stavke.')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {!selectedSeason ? (
              <Button
                type="button"
                disabled={createMutation.isPending || !selectedParcelId}
                onClick={() => createMutation.mutate()}
              >
                {createMutation.isPending ? tr('Kreiranje…') : tr('Kreiraj godišnji plan {{year}}', { year })}
              </Button>
            ) : (
              <>
                {selectedSeason.status !== 'completed' ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={finishMutation.isPending}
                    onClick={() => finishMutation.mutate(selectedSeason.id)}
                  >
                    {finishMutation.isPending ? tr('Završavanje…') : tr('Završi sezonu')}
                  </Button>
                ) : (
                  <span className="text-xs text-muted-foreground">{tr('Sezona je završena.')}</span>
                )}
              </>
            )}
          </div>
        </div>
        {createError ? <p className="text-sm text-danger">{createError}</p> : null}

        <RecommendationStub />

        {selectedSeason ? (
          <ManualPlanWorkspace
            season={selectedSeason}
            year={year}
            categoryFilter={activeFilter}
            saveMessage={saveMessage}
            calendarMessage={calendarMessage}
            onSave={() => {
              setSaveMessage(null)
              saveMutation.mutate(selectedSeason.id)
            }}
            saving={saveMutation.isPending}
            onCalendarMessage={setCalendarMessage}
          />
        ) : null}
      </section>
    </div>
  )
}

function RecommendationStub() {
  return (
    <div className="space-y-2 rounded-lg border border-dashed border-border/80 bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{tr('Predloži plan za sezonu')}</p>
          <p className="text-xs text-muted-foreground">
            {tr('Automatska preporuka na osnovu podataka o zasadu i laboratorijske analize zemljišta.')}
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled>
          Trenutno nije dostupno
        </Button>
      </div>
    </div>
  )
}

function ParcelSummaryCard({
  summary,
  editHref,
}: {
  summary: PlanningParcelSummary
  editHref: string
}) {
  const varieties =
    summary.varieties?.length > 0
      ? summary.varieties.join(', ')
      : summary.default_variety?.trim() || null

  const irrigationParts: string[] = []
  if (summary.has_irrigation) {
    irrigationParts.push(summary.irrigation_type ? `Sistem: ${summary.irrigation_type}` : tr('Sistem označen'))
  }
  if (summary.well_location) {
    irrigationParts.push(tr('Bunarište: {{location}}', { location: summary.well_location }))
  }
  const irrigation = irrigationParts.length > 0 ? irrigationParts.join(' · ') : null

  const soil = summary.latest_soil_analysis
    ? `${summary.latest_soil_analysis.original_filename} (${formatDate(summary.latest_soil_analysis.sampled_on)}${
        summary.latest_soil_analysis.verification_status === 'verified' ? tr(', potvrđena') : tr(', nije potvrđena')
      })`
    : null

  const rows: Array<{ label: string; value: string }> = [
    { label: tr('Parcela'), value: summary.parcel_name },
  ]
  if (summary.area_hectares != null) rows.push({ label: tr('Površina'), value: `${summary.area_hectares} ha` })
  if (varieties) rows.push({ label: 'Sorte', value: varieties })
  if (summary.default_planting_year != null) {
    rows.push({ label: tr('Godina sadnje'), value: String(summary.default_planting_year) })
  }
  if (irrigation) rows.push({ label: tr('Navodnjavanje'), value: irrigation })
  if (summary.organic_status) rows.push({ label: 'Organski status', value: summary.organic_status })
  if (soil) rows.push({ label: 'Poslednja laboratorijska analiza', value: soil })

  return (
    <section className="space-y-3 rounded-xl border border-border/70 bg-background/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">{tr('Sažetak zasada')}</h2>
        <Link to={editHref}>
          <Button type="button" size="sm" variant="outline">
            Izmeni
          </Button>
        </Link>
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        {rows.map((row) => (
          <SummaryRow key={row.label} label={row.label} value={row.value} />
        ))}
      </dl>
    </section>
  )
}

function ManualPlanWorkspace({
  season,
  year,
  categoryFilter,
  saveMessage,
  calendarMessage,
  onSave,
  saving,
  onCalendarMessage,
}: {
  season: PlanningSeason
  year: number
  categoryFilter?: PlanningPlanType
  saveMessage: string | null
  calendarMessage: string | null
  onSave: () => void
  saving: boolean
  onCalendarMessage: (message: string | null) => void
}) {
  const queryClient = useQueryClient()
  const plansQuery = useQuery({
    queryKey: ['planning-plans-detail', season.id],
    queryFn: async () => {
      const plans = await listPlanningPlans(season.id)
      const loaded: PlanningPlan[] = []
      for (const plan of plans) {
        loaded.push(await getPlanningPlan(plan.id))
      }
      return loaded
    },
  })

  const allItems = useMemo(() => {
    const plans = plansQuery.data ?? []
    const rows: Array<PlanningPlanItem & { plan_type: PlanningPlanType }> = []
    for (const plan of plans) {
      for (const item of plan.items) {
        // Ručni plan: prikaži samo korisničke stavke (ne automatske predloge).
        if (item.source !== 'user') continue
        if (categoryFilter && plan.type !== categoryFilter) continue
        rows.push({ ...item, plan_type: plan.type })
      }
    }
    return rows.sort((a, b) => (a.planned_date_from || '').localeCompare(b.planned_date_from || ''))
  }, [plansQuery.data, categoryFilter])

  const typesQuery = useQuery({ queryKey: ['activity-types'], queryFn: listActivityTypes })

  const calendarMutation = useMutation({
    mutationFn: async () => {
      const types = typesQuery.data ?? (await listActivityTypes())
      const trees = await listParcelTrees(season.parcel_id)
      const treeRowById = new Map(trees.map((tree) => [tree.id, tree.row_id]))
      let created = 0
      for (const item of allItems) {
        if (item.status === 'cancelled' || item.status === 'completed') continue
        if (item.related_activity_id) continue
        const date = item.planned_date_from
        if (!date) continue
        const slugs = ACTIVITY_TYPE_SLUG[item.plan_type]
        const type =
          types.find((row) => slugs.includes(row.slug)) ||
          types.find((row) => row.slug === 'maintenance') ||
          types[0]
        if (!type) throw new Error(tr('Nema tipova aktivnosti u katalogu'))

        const products = (item.evidence || []).filter((row) => row.type === 'product' || row.type === 'irrigation')
        const productNote = products
          .map((row) => {
            const name = String(row.name || 'preparat')
            const qty = row.quantity != null ? String(row.quantity) : ''
            const unit = row.unit != null ? String(row.unit) : ''
            return [name, qty, unit].filter(Boolean).join(' ')
          })
          .join('; ')

        const rowId =
          item.scope_type === 'row'
            ? item.scope_id
            : item.scope_type === 'tree'
              ? treeRowById.get(item.scope_id) ?? null
              : null
        if (item.scope_type === 'tree' && !rowId) {
          throw new Error(tr('Ne mogu da mapiram sadnicu na red za kalendar'))
        }

        const activity = await createActivity({
          activity_type_id: type.id,
          performed_on: date,
          scope_type: item.scope_type,
          parcel_id: season.parcel_id,
          row_id: rowId,
          tree_id: item.scope_type === 'tree' ? item.scope_id : null,
          title: item.title,
          description: [item.description, productNote].filter(Boolean).join('\n') || null,
          status: 'planned',
          semantic_type:
            item.plan_type === 'protection'
              ? 'treatment'
              : item.plan_type === 'nutrition'
                ? 'fertilization'
                : 'irrigation',
          plan_item_id: item.id,
          notes: tr('Prebačeno iz godišnjeg plana {{year}}', { year }),
        })
        await updatePlanningPlanItem(item.plan_id, item.id, { related_activity_id: activity.id })
        created += 1
      }
      return created
    },
    onSuccess: async (count) => {
      onCalendarMessage(
        count > 0
          ? tr('{{count}} stavki prebačeno u kalendar / dnevnik.', { count })
          : tr('Nema novih stavki za kalendar (potreban je datum, ili su već prebačene).'),
      )
      await queryClient.invalidateQueries({ queryKey: ['activities'] })
      await queryClient.invalidateQueries({ queryKey: ['planning-plans-detail', season.id] })
      await queryClient.invalidateQueries({ queryKey: ['planning-summary', season.parcel_id] })
    },
    onError: (error) => {
      onCalendarMessage(error instanceof Error ? error.message : tr('Prebacivanje u kalendar nije uspelo'))
    },
  })

  return (
    <div className="space-y-5">
      {season.status !== 'completed' ? (
        <AddPlanItemForm
          season={season}
          defaultCategory={categoryFilter || 'protection'}
          onAdded={async () => {
            await queryClient.invalidateQueries({ queryKey: ['planning-summary', season.parcel_id] })
            await queryClient.invalidateQueries({ queryKey: ['planning-plans-detail', season.id] })
          }}
        />
      ) : null}

      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">
            {tr('Sažetak plana')}
            {categoryFilter ? ` — ${PLAN_TYPE_LABELS[categoryFilter]}` : ''}
          </h3>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" disabled={saving || season.status === 'completed'} onClick={onSave}>
              {saving ? tr('Čuvanje…') : tr('Sačuvaj plan')}
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={calendarMutation.isPending || allItems.length === 0}
              onClick={() => {
                onCalendarMessage(null)
                calendarMutation.mutate()
              }}
            >
              {calendarMutation.isPending ? 'Prebacivanje…' : tr('Prebaci u kalendar')}
            </Button>
          </div>
        </div>
        {saveMessage ? <p className="text-sm text-muted-foreground">{saveMessage}</p> : null}
        {calendarMessage ? <p className="text-sm text-muted-foreground">{calendarMessage}</p> : null}
        {plansQuery.isLoading ? <p className="text-sm text-muted-foreground">{tr('Učitavanje stavki…')}</p> : null}
        {allItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {tr('Nema stavki u planu. Dodajte zaštitu, ishranu ili navodnjavanje pomoću forme iznad.')}
          </p>
        ) : (
          <ul className="space-y-2">
            {allItems.map((item) => (
              <ManualPlanItemCard key={item.id} item={item} planType={item.plan_type} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function AddPlanItemForm({
  season,
  defaultCategory,
  onAdded,
}: {
  season: PlanningSeason
  defaultCategory: PlanningPlanType
  onAdded: () => Promise<void>
}) {
  const [category, setCategory] = useState<PlanningPlanType>(defaultCategory)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [scopeType, setScopeType] = useState<'parcel' | 'row' | 'tree'>('parcel')
  const [rowId, setRowId] = useState('')
  const [treeId, setTreeId] = useState('')
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [products, setProducts] = useState<ProductLine[]>([{ name: '', quantity: '', unit: '' }])
  const [irrigationQty, setIrrigationQty] = useState('')
  const [irrigationUnit, setIrrigationUnit] = useState('m³')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setCategory(defaultCategory)
  }, [defaultCategory])

  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', season.parcel_id],
    queryFn: () => listParcelRows(season.parcel_id),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', season.parcel_id, rowId],
    queryFn: () => listParcelTrees(season.parcel_id, rowId || undefined),
    enabled: scopeType === 'tree',
  })

  const addMutation = useMutation({
    mutationFn: async () => {
      if (!dateFrom) throw new Error('Unesite datum')
      if (!title.trim()) throw new Error(tr('Unesite naziv stavke'))
      if (scopeType === 'row' && !rowId) throw new Error(tr('Izaberite red'))
      if (scopeType === 'tree' && !treeId) throw new Error(tr('Izaberite sadnicu'))

      const existingPlans = await listPlanningPlans(season.id)
      let plan = existingPlans.find((item) => item.type === category)
      if (!plan) {
        plan = await createPlanningPlan(season.id, category)
      }

      const evidence: Array<Record<string, unknown>> = []
      if (category === 'irrigation') {
        if (irrigationQty.trim()) {
          evidence.push({
            type: 'irrigation',
            name: tr('Navodnjavanje'),
            quantity: irrigationQty.trim(),
            unit: irrigationUnit.trim() || 'm³',
          })
        }
      } else {
        for (const line of products) {
          if (!line.name.trim()) continue
          evidence.push({
            type: 'product',
            name: line.name.trim(),
            quantity: line.quantity.trim() || null,
            unit: line.unit.trim() || null,
          })
        }
      }

      return createPlanningPlanItem(plan.id, {
        title: title.trim(),
        description: notes.trim() || null,
        scope_type: scopeType,
        scope_id: scopeType === 'parcel' ? season.parcel_id : scopeType === 'row' ? rowId : treeId,
        planned_date_from: dateFrom,
        planned_date_to: dateTo || dateFrom,
        item_kind: CATEGORY_ITEM_KIND[category],
        stream: 'preventive',
        source: 'user',
        evidence,
        status: 'planned',
        expert_review_status: 'not_required',
        reason: tr('Ručno uneta stavka — {{type}}', { type: PLAN_TYPE_LABELS[category].toLowerCase() }),
      })
    },
    onSuccess: async () => {
      setError(null)
      setTitle('')
      setNotes('')
      setProducts([{ name: '', quantity: '', unit: '' }])
      setIrrigationQty('')
      await onAdded()
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : tr('Dodavanje stavke nije uspelo'))
    },
  })

  return (
    <div className="space-y-3 rounded-lg border border-border/70 bg-background/80 p-3">
      <h3 className="text-sm font-semibold">{tr('Dodaj stavku plana')}</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-1.5">
          <Label>Kategorija</Label>
          <Select
            value={category}
            onChange={(event) => setCategory(event.target.value as PlanningPlanType)}
          >
            <option value="protection">{tr('Zaštita')}</option>
            <option value="nutrition">Ishrana</option>
            <option value="irrigation">{tr('Navodnjavanje')}</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Datum</Label>
          <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>{tr('Datum do (opciono)')}</Label>
          <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label>Obuhvat</Label>
          <Select
            value={scopeType}
            onChange={(event) => setScopeType(event.target.value as 'parcel' | 'row' | 'tree')}
          >
            <option value="parcel">{tr('Ceo zasad')}</option>
            <option value="row">Red</option>
            <option value="tree">{tr('Sadnica')}</option>
          </Select>
        </div>
        {scopeType === 'row' || scopeType === 'tree' ? (
          <div className="space-y-1.5">
            <Label>Red</Label>
            <Select value={rowId} onChange={(event) => setRowId(event.target.value)}>
              <option value="">{tr('Izaberite red')}</option>
              {(rowsQuery.data ?? []).map((row) => (
                <option key={row.id} value={row.id}>
                  Red {String(row.row_number).padStart(2, '0')}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        {scopeType === 'tree' ? (
          <div className="space-y-1.5">
            <Label>{tr('Sadnica')}</Label>
            <Select value={treeId} onChange={(event) => setTreeId(event.target.value)}>
              <option value="">{tr('Izaberite sadnicu')}</option>
              {(treesQuery.data ?? []).map((tree) => (
                <option key={tree.id} value={tree.id}>
                  {tree.public_id}
                </option>
              ))}
            </Select>
          </div>
        ) : null}
        <div className="space-y-1.5 sm:col-span-2 lg:col-span-3">
          <Label>{tr('Naziv stavke')}</Label>
          <Input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={
              category === 'protection'
                ? 'npr. Prskanje protiv bakterioze'
                : category === 'nutrition'
                  ? tr('npr. Prolećno đubrenje')
                  : tr('npr. Navodnjavanje — jun')
            }
          />
        </div>
      </div>

      {category === 'irrigation' ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label>{tr('Količina navodnjavanja')}</Label>
            <Input value={irrigationQty} onChange={(event) => setIrrigationQty(event.target.value)} placeholder="npr. 80" />
          </div>
          <div className="space-y-1.5">
            <Label>Jedinica</Label>
            <Input value={irrigationUnit} onChange={(event) => setIrrigationUnit(event.target.value)} placeholder="m³" />
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <Label>{tr('Preparati i količine')}</Label>
          {products.map((line, index) => (
            <div key={index} className="grid gap-2 sm:grid-cols-3">
              <Input
                placeholder="Preparat"
                value={line.name}
                onChange={(event) => {
                  const next = [...products]
                  next[index] = { ...line, name: event.target.value }
                  setProducts(next)
                }}
              />
              <Input
                placeholder={tr("Količina")}
                value={line.quantity}
                onChange={(event) => {
                  const next = [...products]
                  next[index] = { ...line, quantity: event.target.value }
                  setProducts(next)
                }}
              />
              <Input
                placeholder="Jedinica (kg, L…)"
                value={line.unit}
                onChange={(event) => {
                  const next = [...products]
                  next[index] = { ...line, unit: event.target.value }
                  setProducts(next)
                }}
              />
            </div>
          ))}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setProducts([...products, { name: '', quantity: '', unit: '' }])}
          >
            + Dodaj preparat
          </Button>
        </div>
      )}

      <div className="space-y-1.5">
        <Label>Napomena</Label>
        <Textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <Button type="button" disabled={addMutation.isPending} onClick={() => addMutation.mutate()}>
        {addMutation.isPending ? 'Dodavanje…' : tr('Dodaj u plan')}
      </Button>
    </div>
  )
}

function ManualPlanItemCard({
  item,
  planType,
}: {
  item: PlanningPlanItem & { plan_type?: PlanningPlanType }
  planType: PlanningPlanType
}) {
  const when =
    item.planned_date_from || item.planned_date_to
      ? `${item.planned_date_from ? formatDate(item.planned_date_from) : '—'} → ${
          item.planned_date_to ? formatDate(item.planned_date_to) : '—'
        }`
      : '—'
  const products = (item.evidence || []).filter((row) => row.type === 'product' || row.type === 'irrigation')

  return (
    <li className="rounded-lg border border-border/70 bg-background/80 px-3 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {PLAN_TYPE_LABELS[planType]}
          </p>
          <p className="font-medium">{item.title}</p>
        </div>
        <span className="text-[11px] text-muted-foreground">{itemStatusLabel(item.status)}</span>
      </div>
      <dl className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
        <div>
          <dt className="font-medium text-foreground/80">Kada</dt>
          <dd>{when}</dd>
        </div>
        <div>
          <dt className="font-medium text-foreground/80">Gde</dt>
          <dd>
            {item.scope_type === 'parcel'
              ? tr('Ceo zasad')
              : item.scope_type === 'row'
                ? tr('Red')
                : tr('Sadnica')}
          </dd>
        </div>
        {products.length > 0 ? (
          <div className="sm:col-span-2">
            <dt className="font-medium text-foreground/80">
              {planType === 'irrigation' ? tr('Količina') : 'Preparati'}
            </dt>
            <dd>
              {products
                .map((row) =>
                  [row.name, row.quantity, row.unit].filter((part) => part != null && String(part).trim()).join(' '),
                )
                .join(' · ')}
            </dd>
          </div>
        ) : null}
        {item.description ? (
          <div className="sm:col-span-2">
            <dt className="font-medium text-foreground/80">Napomena</dt>
            <dd>{item.description}</dd>
          </div>
        ) : null}
      </dl>
      {item.related_activity_id ? (
        <div className="mt-3">
          <Link to={`/activities/${item.related_activity_id}`}>
            <Button type="button" size="sm" variant="outline">
              Otvori u dnevniku
            </Button>
          </Link>
        </div>
      ) : null}
    </li>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function NavChip({ to, active, children }: { to: string; active: boolean; children: string }) {
  return (
    <Link
      to={to}
      className={
        active
          ? 'rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground'
          : 'rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted/40'
      }
    >
      {children}
    </Link>
  )
}
