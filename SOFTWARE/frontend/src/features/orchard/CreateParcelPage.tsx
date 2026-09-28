import { useMemo, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import { createParcel } from '@/features/orchard/api'
import { PlantingLayoutEditor, gapKey, type PlantingPlan } from '@/features/orchard/PlantingLayoutEditor'
import { createParcelSchema, type CreateParcelValues, type VarietyValues } from '@/features/orchard/schemas'
import { DEFAULT_VARIETIES, mainVarietyName, nextVarietyColor, roleLabel } from '@/features/orchard/varieties'
import { formatNumber } from '@/shared/lib/format'
import { BackLink } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

const currentYear = new Date().getFullYear()

export function CreateParcelPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'details' | 'layout'>('details')
  const [selectedVariety, setSelectedVariety] = useState(DEFAULT_VARIETIES[0].name)
  const [plan, setPlan] = useState<PlantingPlan | null>(null)

  const form = useForm<CreateParcelValues>({
    resolver: zodResolver(createParcelSchema),
    defaultValues: {
      name: '',
      area_hectares: 2.4,
      row_count: 26,
      trees_per_row: 73,
      row_spacing_m: 5,
      tree_spacing_m: 3.5,
      planting_year: 2022,
      starting_tree_number: 1,
      maps_url: '',
      varieties: DEFAULT_VARIETIES,
    },
  })

  const varieties = form.watch('varieties')
  const rowCount = Number(form.watch('row_count') || 0)
  const treesPerRow = Number(form.watch('trees_per_row') || 0)

  const mutation = useMutation({
    mutationFn: createParcel,
    onSuccess: (parcel) => {
      void navigate(`/orchard/${parcel.id}`)
    },
  })

  function buildPlan(nextRowCount: number, nextTrees: number, nextVarieties: VarietyValues[]): PlantingPlan {
    const main = mainVarietyName(nextVarieties)
    const previous = plan
    const rowVarieties = Array.from({ length: nextRowCount }, (_, index) => {
      const kept = previous?.rowVarieties[index]
      if (kept && nextVarieties.some((item) => item.name === kept)) return kept
      return main
    })
    const missing = new Set<string>()
    for (const key of previous?.missing ?? []) {
      const [row, pos] = key.split(':').map(Number)
      if (row >= 1 && row <= nextRowCount && pos >= 1 && pos <= nextTrees) missing.add(key)
    }
    return { rowVarieties, missing }
  }

  function goToLayout() {
    void form.handleSubmit((values) => {
      const nextPlan = buildPlan(values.row_count, values.trees_per_row, values.varieties)
      setPlan(nextPlan)
      setSelectedVariety(mainVarietyName(values.varieties))
      setStep('layout')
    })()
  }

  function generate() {
    if (!plan) return
    const values = form.getValues()
    mutation.mutate({
      name: values.name,
      area_hectares: values.area_hectares,
      row_count: values.row_count,
      trees_per_row: values.trees_per_row,
      row_spacing_m: values.row_spacing_m,
      tree_spacing_m: values.tree_spacing_m,
      default_variety: mainVarietyName(values.varieties),
      varieties: values.varieties,
      planting_year: values.planting_year,
      starting_tree_number: values.starting_tree_number,
      maps_url: values.maps_url?.trim() || null,
      row_plan: plan.rowVarieties.map((variety, index) => {
        const rowNumber = index + 1
        const missing_positions: number[] = []
        for (let position = 1; position <= values.trees_per_row; position += 1) {
          if (plan.missing.has(gapKey(rowNumber, position))) missing_positions.push(position)
        }
        return { row_number: rowNumber, variety, missing_positions }
      }),
    })
  }

  const planted = useMemo(() => {
    if (!plan) return 0
    return rowCount * treesPerRow - plan.missing.size
  }, [plan, rowCount, treesPerRow])

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Plan voćnjaka</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">
            {step === 'details' ? 'Parcela i zasađene sorte' : 'Označite plan sadnje'}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {step === 'details'
              ? 'Opišite blok i sorte lesnika. Zasad se pravi nakon što označite redove i praznine.'
              : 'Obojite svaki red sortom i kliknite na mesta bez sadnica. Samo ovaj plan postaje zasad.'}
          </p>
        </div>
        <BackLink fallback="/orchard">Nazad na zasade</BackLink>
      </div>

      {step === 'details' ? (
        <form className="space-y-6 rounded-xl border border-border bg-card p-4 sm:p-6" onSubmit={(event) => event.preventDefault()}>
          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Naziv parcele" error={form.formState.errors.name?.message}>
              <Input id="name" placeholder="Severna padina" {...form.register('name')} />
            </Field>
            <Field label="Površina (ha)" error={form.formState.errors.area_hectares?.message}>
              <Input id="area_hectares" type="number" step="0.0001" {...form.register('area_hectares')} />
            </Field>
            <Field
              className="md:col-span-2"
              label="Google Maps link"
              error={form.formState.errors.maps_url?.message}
              hint="U Google Maps otvorite zasad, zatim Deli → Kopiraj link."
            >
              <Input
                id="maps_url"
                type="url"
                placeholder="https://maps.app.goo.gl/…"
                {...form.register('maps_url')}
              />
            </Field>
            <Field label="Broj redova" error={form.formState.errors.row_count?.message}>
              <Input id="row_count" type="number" min={1} {...form.register('row_count')} />
            </Field>
            <Field label="Sadnica u redu" error={form.formState.errors.trees_per_row?.message}>
              <Input id="trees_per_row" type="number" min={1} {...form.register('trees_per_row')} />
            </Field>
            <Field label="Razmak redova (m)" error={form.formState.errors.row_spacing_m?.message}>
              <Input id="row_spacing_m" type="number" step="0.01" {...form.register('row_spacing_m')} />
            </Field>
            <Field label="Razmak sadnica (m)" error={form.formState.errors.tree_spacing_m?.message}>
              <Input id="tree_spacing_m" type="number" step="0.01" {...form.register('tree_spacing_m')} />
            </Field>
            <Field label="Godina sadnje" error={form.formState.errors.planting_year?.message}>
              <Input
                id="planting_year"
                type="number"
                min={1900}
                max={currentYear + 1}
                {...form.register('planting_year')}
              />
            </Field>
            <Field label="Početni broj stabla" error={form.formState.errors.starting_tree_number?.message}>
              <Input id="starting_tree_number" type="number" min={1} {...form.register('starting_tree_number')} />
            </Field>
          </div>

          <div className="space-y-3 border-t border-border pt-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-medium">Zasađene sorte</h2>
                <p className="text-sm text-muted-foreground">Dodajte svaku sortu u bloku i izaberite boju na mapi.</p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  const next = [
                    ...varieties,
                    { name: '', role: 'pollinator' as const, color: nextVarietyColor(varieties) },
                  ]
                  form.setValue('varieties', next, { shouldValidate: true })
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
                        const next = varieties.map((variety, varietyIndex) =>
                          varietyIndex === index ? { ...variety, name: event.target.value } : variety,
                        )
                        form.setValue('varieties', next, { shouldValidate: true })
                      }}
                    />
                  </Field>
                  <Field label="Uloga">
                    <Select
                      value={item.role}
                      onChange={(event) => {
                        const next = varieties.map((variety, varietyIndex) =>
                          varietyIndex === index
                            ? { ...variety, role: event.target.value as VarietyValues['role'] }
                            : variety,
                        )
                        form.setValue('varieties', next, { shouldValidate: true })
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
                        const next = varieties.map((variety, varietyIndex) =>
                          varietyIndex === index ? { ...variety, color: event.target.value } : variety,
                        )
                        form.setValue('varieties', next, { shouldValidate: true })
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

          <div className="flex items-center justify-between border-t border-border pt-5">
            <p className="font-mono text-sm text-muted-foreground">
              {rowCount > 0 && treesPerRow > 0
                ? `${rowCount} redova × ${treesPerRow} mesta = ${formatNumber(rowCount * treesPerRow)} mogućih sadnica`
                : 'Unesite strukturu da nastavite'}
            </p>
            <Button type="button" onClick={goToLayout}>
              Nastavi na plan sadnje
            </Button>
          </div>
        </form>
      ) : plan ? (
        <div className="space-y-6 rounded-xl border border-border bg-card p-6">
          <PlantingLayoutEditor
            varieties={varieties}
            rowCount={rowCount}
            treesPerRow={treesPerRow}
            plan={plan}
            selectedVariety={selectedVariety}
            onSelectVariety={setSelectedVariety}
            onChange={setPlan}
          />
          <div className="flex items-center justify-between border-t border-border pt-5">
            <Button type="button" variant="outline" onClick={() => setStep('details')}>
              Nazad
            </Button>
            <div className="flex items-center gap-4">
              <p className="font-mono text-sm text-muted-foreground">
                Nastaće {rowCount} redova i {formatNumber(planted)} stabala
              </p>
              <Button type="button" onClick={generate} disabled={mutation.isPending || planted < 1}>
                {mutation.isPending ? 'Pravljenje voćnjaka…' : 'Napravi zasad'}
              </Button>
            </div>
          </div>
          {mutation.error ? <p className="text-sm text-danger">{mutation.error.message}</p> : null}
        </div>
      ) : null}
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
