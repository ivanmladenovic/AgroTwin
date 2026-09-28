import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate, useParams } from 'react-router-dom'

import { deleteParcel, getOrchardTwin, updateParcel } from '@/features/orchard/api'
import { PlantingLayoutEditor, gapKey, type PlantingPlan } from '@/features/orchard/PlantingLayoutEditor'
import { editParcelSchema, type EditParcelValues, type VarietyValues } from '@/features/orchard/schemas'
import { mainVarietyName, nextVarietyColor, roleLabel, varietiesFromTwin } from '@/features/orchard/varieties'
import type { OrchardTwin } from '@/shared/api/types'
import { formatNumber } from '@/shared/lib/format'
import { BackLink } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

const currentYear = new Date().getFullYear()

function planFromTwin(twin: OrchardTwin, varieties: VarietyValues[]): PlantingPlan {
  const rowCount = twin.parcel.row_count ?? twin.rows.length
  const treesPerRow = twin.parcel.trees_per_row ?? 0
  const main = mainVarietyName(varieties)
  const byRow = new Map(twin.rows.map((row) => [row.row_number, row.variety]))
  const active = new Set(
    twin.trees
      .filter((tree) => tree.status === 'active')
      .map((tree) => gapKey(tree.row_number, tree.position_in_row)),
  )
  const rowVarieties = Array.from({ length: rowCount }, (_, index) => {
    const rowNumber = index + 1
    const named = byRow.get(rowNumber)
    if (named && varieties.some((item) => item.name === named)) return named
    const tree = twin.trees.find((item) => item.row_number === rowNumber && item.status === 'active' && item.variety)
    if (tree?.variety && varieties.some((item) => item.name === tree.variety)) return tree.variety
    return main
  })
  const missing = new Set<string>()
  for (let row = 1; row <= rowCount; row += 1) {
    for (let position = 1; position <= treesPerRow; position += 1) {
      const key = gapKey(row, position)
      if (!active.has(key)) missing.add(key)
    }
  }
  return { rowVarieties, missing }
}

export function EditParcelPage() {
  const { parcelId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedVariety, setSelectedVariety] = useState('')
  const [plan, setPlan] = useState<PlantingPlan | null>(null)

  const twinQuery = useQuery({
    queryKey: ['orchard-twin', parcelId],
    queryFn: () => getOrchardTwin(parcelId!),
    enabled: Boolean(parcelId),
  })

  const form = useForm<EditParcelValues>({
    resolver: zodResolver(editParcelSchema),
    defaultValues: {
      name: '',
      area_hectares: 1,
      planting_year: currentYear,
      maps_url: '',
      varieties: [],
    },
  })

  useEffect(() => {
    const twin = twinQuery.data
    if (!twin) return
    const varieties = varietiesFromTwin(twin)
    form.reset({
      name: twin.parcel.name,
      area_hectares: Number(twin.parcel.area_hectares ?? 0) || 1,
      planting_year: twin.parcel.default_planting_year ?? currentYear,
      maps_url: twin.parcel.maps_url ?? '',
      varieties,
    })
    setPlan(planFromTwin(twin, varieties))
    setSelectedVariety(mainVarietyName(varieties))
  }, [form, twinQuery.data])

  const varieties = form.watch('varieties')
  const twin = twinQuery.data
  const rowCount = twin?.parcel.row_count ?? 0
  const treesPerRow = twin?.parcel.trees_per_row ?? 0
  const planted = useMemo(() => {
    if (!plan) return 0
    return rowCount * treesPerRow - plan.missing.size
  }, [plan, rowCount, treesPerRow])

  const saveMutation = useMutation({
    mutationFn: (values: EditParcelValues) => {
      if (!parcelId || !plan) throw new Error('Parcela nije učitana')
      return updateParcel(parcelId, {
        name: values.name,
        area_hectares: values.area_hectares,
        maps_url: values.maps_url?.trim() || null,
        planting_year: values.planting_year,
        varieties: values.varieties,
        row_plan: plan.rowVarieties.map((variety, index) => {
          const rowNumber = index + 1
          const missing_positions: number[] = []
          for (let position = 1; position <= treesPerRow; position += 1) {
            if (plan.missing.has(gapKey(rowNumber, position))) missing_positions.push(position)
          }
          return { row_number: rowNumber, variety, missing_positions }
        }),
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['parcels'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin', parcelId] })
      void navigate(`/orchard/${parcelId}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteParcel(parcelId!),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['parcels'] })
      void navigate('/orchard')
    },
  })

  if (!parcelId) return null
  if (twinQuery.isLoading || !twin || !plan) {
    return <div className="p-6 text-sm text-muted-foreground">Učitavanje parcele…</div>
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Zasadi</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Izmena: {twin.parcel.name}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Izmenite naziv, sorte, boje redova i prazna mesta. Veličina mreže ostaje ista.
          </p>
        </div>
        <BackLink fallback={`/orchard/${parcelId}`}>Nazad na mapu</BackLink>
      </div>

      <form
        className="space-y-6 rounded-xl border border-border bg-card p-4 sm:p-6"
        onSubmit={form.handleSubmit((values) => saveMutation.mutate(values))}
      >
        <div className="grid gap-5 md:grid-cols-2">
          <Field label="Naziv parcele" error={form.formState.errors.name?.message}>
            <Input {...form.register('name')} />
          </Field>
          <Field label="Površina (ha)" error={form.formState.errors.area_hectares?.message}>
            <Input type="number" step="0.0001" {...form.register('area_hectares')} />
          </Field>
          <Field
            className="md:col-span-2"
            label="Google Maps link"
            error={form.formState.errors.maps_url?.message}
            hint="U Google Maps otvorite zasad, zatim Deli → Kopiraj link."
          >
            <Input type="url" placeholder="https://maps.app.goo.gl/…" {...form.register('maps_url')} />
          </Field>
          <Field label="Godina sadnje" error={form.formState.errors.planting_year?.message}>
            <Input type="number" min={1900} max={currentYear + 1} {...form.register('planting_year')} />
          </Field>
          <div className="space-y-2">
            <Label>Struktura</Label>
            <p className="pt-2 font-mono text-sm text-muted-foreground">
              {rowCount} redova × {treesPerRow} mesta
            </p>
          </div>
        </div>

        <div className="space-y-3 border-t border-border pt-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-medium">Zasađene sorte</h2>
              <p className="text-sm text-muted-foreground">Preimenujte, promenite boju ili dodajte sorte, zatim obojite redove.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                form.setValue(
                  'varieties',
                  [...varieties, { name: '', role: 'pollinator', color: nextVarietyColor(varieties) }],
                  { shouldValidate: true },
                )
              }}
            >
              Dodaj sortu
            </Button>
          </div>
          {form.formState.errors.varieties?.message ? (
            <p className="text-xs text-danger">{form.formState.errors.varieties.message}</p>
          ) : null}
          <div className="space-y-3">
            {varieties.map((item, index) => (
              <div key={`${item.color}-${index}`} className="grid gap-3 border border-border p-3 md:grid-cols-[1fr_10rem_6rem_auto]">
                <Field label="Sorta" error={form.formState.errors.varieties?.[index]?.name?.message}>
                  <Input
                    value={item.name}
                    onChange={(event) => {
                      form.setValue(
                        'varieties',
                        varieties.map((variety, varietyIndex) =>
                          varietyIndex === index ? { ...variety, name: event.target.value } : variety,
                        ),
                        { shouldValidate: true },
                      )
                    }}
                  />
                </Field>
                <Field label="Uloga">
                  <Select
                    value={item.role}
                    onChange={(event) => {
                      form.setValue(
                        'varieties',
                        varieties.map((variety, varietyIndex) =>
                          varietyIndex === index
                            ? { ...variety, role: event.target.value as VarietyValues['role'] }
                            : variety,
                        ),
                        { shouldValidate: true },
                      )
                    }}
                  >
                    <option value="main">{roleLabel('main')}</option>
                    <option value="pollinator">{roleLabel('pollinator')}</option>
                    <option value="other">{roleLabel('other')}</option>
                  </Select>
                </Field>
                <Field label="Boja">
                  <Input
                    type="color"
                    value={item.color}
                    onChange={(event) => {
                      form.setValue(
                        'varieties',
                        varieties.map((variety, varietyIndex) =>
                          varietyIndex === index ? { ...variety, color: event.target.value } : variety,
                        ),
                        { shouldValidate: true },
                      )
                    }}
                  />
                </Field>
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={varieties.length <= 1}
                    onClick={() => {
                      form.setValue(
                        'varieties',
                        varieties.filter((_, varietyIndex) => varietyIndex !== index),
                        { shouldValidate: true },
                      )
                    }}
                  >
                    Ukloni
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <PlantingLayoutEditor
            varieties={varieties}
            rowCount={rowCount}
            treesPerRow={treesPerRow}
            plan={plan}
            selectedVariety={selectedVariety || mainVarietyName(varieties)}
            onSelectVariety={setSelectedVariety}
            onChange={setPlan}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
          <Button
            type="button"
            variant="outline"
            disabled={deleteMutation.isPending}
            onClick={() => {
              if (!window.confirm(`Obrisati ${twin.parcel.name}? Stabla, dnevnik i zapažanja na ovoj parceli biće uklonjeni.`)) {
                return
              }
              deleteMutation.mutate()
            }}
          >
            {deleteMutation.isPending ? 'Brisanje…' : 'Obriši parcelu'}
          </Button>
          <div className="flex items-center gap-4">
            <p className="font-mono text-sm text-muted-foreground">
              {formatNumber(planted)} stabala nakon čuvanja
            </p>
            <Button type="submit" disabled={saveMutation.isPending || planted < 1}>
              {saveMutation.isPending ? 'Čuvanje…' : 'Sačuvaj izmene'}
            </Button>
          </div>
        </div>
        {saveMutation.error ? (
          <p className="text-sm text-danger">
            {saveMutation.error instanceof Error ? saveMutation.error.message : 'Čuvanje nije uspelo'}
          </p>
        ) : null}
        {deleteMutation.error ? (
          <p className="text-sm text-danger">
            {deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Brisanje nije uspelo'}
          </p>
        ) : null}
      </form>
    </div>
  )
}

function Field({
  label,
  error,
  hint,
  className,
  children,
}: {
  label: string
  error?: string
  hint?: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={className ? `space-y-2 ${className}` : 'space-y-2'}>
      <Label>{label}</Label>
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  )
}
