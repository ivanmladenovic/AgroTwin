import { useEffect, useRef, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { MapPinned, Plus, X } from 'lucide-react'
import { useFieldArray, useForm, type UseFormRegister } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import { createActivity, listActivityTypes, uploadSoilAnalysis } from '@/features/journal/api'
import {
  activityLineKind,
  activityLineSectionLabel,
  emptyActivityLineItem,
  emptyIrrigationEquipmentItem,
  emptyIrrigationFuelItem,
  isIrrigationFuelName,
  parseOptionalNumber,
  type ActivityLineKind,
} from '@/features/journal/activityLineItems'
import { defaultActivityStatus } from '@/features/journal/labels'
import { OrchardPickerDialog } from '@/features/journal/OrchardPickerDialog'
import {
  emptySoilSample,
  soilSamplesError,
  SoilAnalysisSamples,
  type SoilSampleDraft,
} from '@/features/journal/SoilAnalysisSamples'
import { activityFormSchema, type ActivityFormValues } from '@/features/journal/schemas'
import { todayKey } from '@/features/journal/calendar'
import { listParcelRows, listParcels, listParcelTrees } from '@/features/orchard/api'
import type { ActivityScope, ActivityStatus } from '@/shared/api/types'
import { rowLabel } from '@/shared/lib/format'
import { BackLink } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

type Prefill = {
  scope_type?: ActivityScope
  parcel_id?: string
  row_id?: string
  tree_id?: string
  return_to?: string
  performed_on?: string
  status?: ActivityStatus
}

export function ActivityForm({ prefill }: { prefill: Prefill }) {
  const navigate = useNavigate()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [soilSamples, setSoilSamples] = useState<SoilSampleDraft[]>([])
  const [soilError, setSoilError] = useState<string | null>(null)
  const typesQuery = useQuery({ queryKey: ['activity-types'], queryFn: listActivityTypes })
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })

  const form = useForm<ActivityFormValues>({
    resolver: zodResolver(activityFormSchema),
    defaultValues: {
      activity_type_id: '',
      performed_on: prefill.performed_on || todayKey(),
      status: prefill.status || defaultActivityStatus(prefill.performed_on || todayKey(), todayKey()),
      scope_type: prefill.scope_type ?? 'parcel',
      parcel_id: prefill.parcel_id ?? '',
      row_id: prefill.row_id ?? '',
      row_ids: prefill.row_id ? [prefill.row_id] : [],
      tree_id: prefill.tree_id ?? '',
      description: '',
      line_items: [emptyActivityLineItem('other')],
    },
  })

  const items = useFieldArray({ control: form.control, name: 'line_items' })
  const activityTypeId = form.watch('activity_type_id')
  const scope = form.watch('scope_type')
  const performedOn = form.watch('performed_on')
  const parcelId = form.watch('parcel_id') || prefill.parcel_id || ''
  const rowId = form.watch('row_id') || prefill.row_id || ''
  const rowIds = form.watch('row_ids')
  const treeId = form.watch('tree_id')
  const previousScope = useRef(scope)
  const statusTouched = useRef(Boolean(prefill.status))

  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
    enabled: Boolean(parcelId) && scope !== 'parcel',
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId, rowId],
    queryFn: () => listParcelTrees(parcelId, rowId),
    enabled: Boolean(parcelId && rowId) && scope === 'tree',
  })

  const parcelName = (parcelsQuery.data ?? []).find((parcel) => parcel.id === parcelId)?.name
  const rows = rowsQuery.data ?? []
  const selectedTree = (treesQuery.data ?? []).find((tree) => tree.id === treeId)
  const selectedType = (typesQuery.data ?? []).find((item) => item.id === activityTypeId)
  const lineKind = activityLineKind(selectedType)
  const previousLineKind = useRef(lineKind)

  useEffect(() => {
    if (typesQuery.data?.[0] && !form.getValues('activity_type_id')) {
      form.setValue('activity_type_id', typesQuery.data[0].id)
    }
  }, [form, typesQuery.data])

  useEffect(() => {
    if (previousLineKind.current === lineKind) return
    previousLineKind.current = lineKind
    form.setValue('line_items', lineKind === 'irrigation' ? [emptyIrrigationFuelItem()] : [emptyActivityLineItem(lineKind)])
    if (lineKind === 'soil_analysis') {
      form.setValue('scope_type', 'parcel')
      setSoilSamples((current) => (current.length ? current : [emptySoilSample(form.getValues('performed_on'))]))
    } else {
      setSoilSamples([])
      setSoilError(null)
    }
  }, [form, lineKind])

  useEffect(() => {
    const parcels = parcelsQuery.data ?? []
    if (prefill.parcel_id && parcels.some((parcel) => parcel.id === prefill.parcel_id)) {
      form.setValue('parcel_id', prefill.parcel_id)
      return
    }
    if (!prefill.parcel_id && parcels[0] && !form.getValues('parcel_id')) {
      form.setValue('parcel_id', parcels[0].id)
    }
  }, [form, parcelsQuery.data, prefill.parcel_id])

  useEffect(() => {
    const currentRows = rowsQuery.data ?? []
    if (prefill.row_id && currentRows.some((row) => row.id === prefill.row_id)) {
      form.setValue('row_id', prefill.row_id)
      if (!form.getValues('row_ids').length) form.setValue('row_ids', [prefill.row_id])
    }
  }, [form, prefill.row_id, rowsQuery.data])

  useEffect(() => {
    const trees = treesQuery.data ?? []
    if (prefill.tree_id && trees.some((tree) => tree.id === prefill.tree_id)) {
      form.setValue('tree_id', prefill.tree_id)
    }
  }, [form, prefill.tree_id, treesQuery.data])

  useEffect(() => {
    if (previousScope.current === scope) return
    previousScope.current = scope
    if (scope === 'parcel') {
      form.setValue('row_id', '')
      form.setValue('row_ids', [])
      form.setValue('tree_id', '')
    }
    if (scope === 'row') {
      form.setValue('tree_id', '')
    }
  }, [form, scope])

  useEffect(() => {
    if (statusTouched.current) return
    form.setValue('status', defaultActivityStatus(performedOn, todayKey()))
  }, [form, performedOn])

  const mutation = useMutation({
    mutationFn: async (payload: Parameters<typeof createActivity>[0]) => {
      const activity = await createActivity(payload)
      if (lineKind === 'soil_analysis') {
        for (const sample of soilSamples) {
          if (!sample.file || !sample.tree_id) continue
          await uploadSoilAnalysis(activity.id, {
            file: sample.file,
            tree_id: sample.tree_id,
            sampled_on: sample.sampled_on,
          })
        }
      }
      return activity
    },
    onSuccess: (activity) => {
      const params = new URLSearchParams()
      if (prefill.return_to) params.set('returnTo', prefill.return_to)
      void navigate(`/activities/${activity.id}?${params.toString()}`)
    },
  })

  function toggleRow(rowIdValue: string) {
    const current = form.getValues('row_ids')
    const next = current.includes(rowIdValue)
      ? current.filter((id) => id !== rowIdValue)
      : [...current, rowIdValue]
    form.setValue('row_ids', next, { shouldValidate: true })
    form.setValue('row_id', next[0] ?? '')
  }

  function setAllRows() {
    const ids = rows.map((row) => row.id)
    form.setValue('row_ids', ids, { shouldValidate: true })
    form.setValue('row_id', ids[0] ?? '')
  }

  function clearRows() {
    form.setValue('row_ids', [], { shouldValidate: true })
    form.setValue('row_id', '')
  }

  return (
    <form
      className="space-y-5"
      onSubmit={form.handleSubmit((values) => {
        if (lineKind === 'soil_analysis') {
          const error = soilSamplesError(soilSamples)
          setSoilError(error)
          if (error) return
        }
        const lineItems =
          lineKind === 'soil_analysis'
            ? []
            : values.line_items
                .map((item, index) => {
            const quantity = parseOptionalNumber(item.quantity)
            const amount = parseOptionalNumber(item.amount)
            const isFuel = lineKind === 'irrigation' && (index === 0 || isIrrigationFuelName(item.name))
            const typedName = isFuel ? '' : item.name?.trim() || ''
            const hasValues = quantity != null || amount != null || Boolean(typedName)
            const name = typedName || (isFuel && hasValues ? 'Nafta' : '')
            const unit = isFuel
              ? quantity != null
                ? 'L'
                : null
              : lineKind === 'fertilization'
                ? quantity != null
                  ? 'kg'
                  : null
                : item.unit?.trim() || null
            return {
              name: name || null,
              quantity,
              unit,
              volume: null,
              volume_unit: null,
              amount,
            }
          })
          .filter((item) => item.name || item.quantity != null || item.amount != null)
        const first = lineItems.find((item) => item.quantity != null && item.unit !== 'EUR')
        mutation.mutate({
          activity_type_id: values.activity_type_id,
          performed_on: values.performed_on,
          scope_type: lineKind === 'soil_analysis' ? 'parcel' : values.scope_type,
          parcel_id: values.parcel_id,
          row_id: lineKind === 'soil_analysis' || values.scope_type === 'parcel' ? null : values.row_id || values.row_ids[0] || null,
          row_ids: lineKind === 'soil_analysis' || values.scope_type !== 'row' ? [] : values.row_ids,
          tree_id: lineKind === 'soil_analysis' || values.scope_type !== 'tree' ? null : values.tree_id || null,
          description: values.description || null,
          quantity: first?.quantity ?? null,
          unit: first?.unit || null,
          line_items: lineItems,
          status: values.status,
        })
      })}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Tip aktivnosti" error={form.formState.errors.activity_type_id?.message}>
          <Select {...form.register('activity_type_id')}>
            <option value="">Izaberite tip</option>
            {(typesQuery.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Datum" error={form.formState.errors.performed_on?.message}>
          <Input type="date" {...form.register('performed_on')} />
        </Field>
        <Field label="Status">
          <Select
            {...form.register('status', {
              onChange: () => {
                statusTouched.current = true
              },
            })}
          >
            <option value="completed">Urađeno</option>
            <option value="planned">Planirano</option>
            <option value="in_progress">U toku</option>
          </Select>
        </Field>
        <Field label="Obuhvat">
          <Select {...form.register('scope_type')} disabled={lineKind === 'soil_analysis'}>
            <option value="parcel">Parcela</option>
            <option value="row">Red</option>
            <option value="tree">Stablo</option>
          </Select>
        </Field>
      </div>

      {parcelName ? <p className="text-sm text-muted-foreground">Zasad: {parcelName}</p> : null}

      {scope === 'row' && lineKind !== 'soil_analysis' ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label>Redovi</Label>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" size="sm" onClick={setAllRows} disabled={!rows.length}>
                Svi redovi
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={() => setPickerOpen(true)} disabled={!parcelId}>
                <MapPinned className="h-4 w-4" />
                Pregled zasada
              </Button>
            </div>
          </div>
          <div className="grid max-h-56 grid-cols-2 gap-2 overflow-auto rounded-xl border border-border p-3 sm:grid-cols-3 md:grid-cols-4">
            {rows.map((row) => {
              const checked = rowIds.includes(row.id)
              return (
                <label key={row.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleRow(row.id)}
                    className="h-5 w-5 accent-primary"
                  />
                  {rowLabel(row.row_number)}
                </label>
              )
            })}
          </div>
          {form.formState.errors.row_ids?.message ? (
            <p className="text-xs text-danger">{form.formState.errors.row_ids.message}</p>
          ) : null}
        </div>
      ) : null}

      {scope === 'tree' && lineKind !== 'soil_analysis' ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Red" error={form.formState.errors.row_id?.message}>
            <Select
              value={rowId}
              onChange={(event) => {
                form.setValue('row_id', event.target.value, { shouldValidate: true })
                form.setValue('row_ids', event.target.value ? [event.target.value] : [])
                form.setValue('tree_id', '')
              }}
            >
              <option value="">Izaberite red</option>
              {rows.map((row) => (
                <option key={row.id} value={row.id}>
                  {rowLabel(row.row_number)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Stablo" error={form.formState.errors.tree_id?.message}>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Select {...form.register('tree_id')} className="flex-1">
                <option value="">{rowId ? 'Izaberite stablo' : 'Prvo izaberite red'}</option>
                {(treesQuery.data ?? []).map((tree) => (
                  <option key={tree.id} value={tree.id}>
                    {tree.public_id}
                  </option>
                ))}
              </Select>
              <Button type="button" variant="outline" onClick={() => setPickerOpen(true)} disabled={!parcelId}>
                <MapPinned className="h-4 w-4" />
                Pregled
              </Button>
            </div>
            {selectedTree ? (
              <p className="text-xs text-muted-foreground">Izabrano: {selectedTree.public_id}</p>
            ) : null}
          </Field>
        </div>
      ) : null}

      {lineKind === 'soil_analysis' ? (
        <div className="space-y-2">
          <SoilAnalysisSamples parcelId={parcelId} samples={soilSamples} onChange={setSoilSamples} />
          {soilError ? <p className="text-xs text-danger">{soilError}</p> : null}
        </div>
      ) : lineKind === 'irrigation' ? (
        <>
          <div className="space-y-2">
            <Label>Nafta</Label>
            {items.fields[0] ? (
              <ActivityLineRow
                key={items.fields[0].id}
                kind="irrigation"
                variant="fuel"
                index={0}
                register={form.register}
                canRemove={false}
                isLast={false}
                onRemove={() => undefined}
                onAdd={() => undefined}
              />
            ) : null}
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Oprema</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => items.append(emptyIrrigationEquipmentItem())}
              >
                <Plus className="h-4 w-4" />
                Dodaj opremu
              </Button>
            </div>
            {items.fields.slice(1).map((field, offset) => {
              const index = offset + 1
              return (
                <ActivityLineRow
                  key={field.id}
                  kind="irrigation"
                  variant="equipment"
                  index={index}
                  register={form.register}
                  canRemove
                  isLast={false}
                  onRemove={() => items.remove(index)}
                  onAdd={() => undefined}
                />
              )
            })}
          </div>
        </>
      ) : (
        <div className="space-y-2">
          <Label>{activityLineSectionLabel(lineKind)}</Label>
          {items.fields.map((field, index) => (
            <ActivityLineRow
              key={field.id}
              kind={lineKind}
              index={index}
              register={form.register}
              canRemove={items.fields.length > 1}
              isLast={index === items.fields.length - 1}
              onRemove={() => items.remove(index)}
              onAdd={() => items.append(emptyActivityLineItem(lineKind))}
            />
          ))}
        </div>
      )}

      <Field label="Opis">
        <Textarea rows={3} {...form.register('description')} />
      </Field>
      {mutation.isError ? (
        <p className="text-sm text-danger">{mutation.error instanceof Error ? mutation.error.message : 'Čuvanje nije uspelo'}</p>
      ) : null}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Čuvanje…' : 'Sačuvaj'}
        </Button>
        <BackLink fallback={prefill.return_to || '/journal'}>Otkaži</BackLink>
      </div>

      {pickerOpen && parcelId ? (
        <OrchardPickerDialog
          parcelId={parcelId}
          mode={scope === 'tree' ? 'tree' : 'rows'}
          selectedRowIds={rowIds}
          selectedTreeId={treeId || null}
          onToggleRow={toggleRow}
          onSelectAllRows={setAllRows}
          onClearRows={clearRows}
          onSelectTree={(nextTreeId, nextRowId) => {
            form.setValue('tree_id', nextTreeId, { shouldValidate: true })
            form.setValue('row_id', nextRowId, { shouldValidate: true })
            form.setValue('row_ids', [nextRowId])
          }}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
    </form>
  )
}

function ActivityLineRow({
  kind,
  variant,
  index,
  register,
  canRemove,
  isLast,
  onRemove,
  onAdd,
}: {
  kind: ActivityLineKind
  variant?: 'fuel' | 'equipment'
  index: number
  register: UseFormRegister<ActivityFormValues>
  canRemove: boolean
  isLast: boolean
  onRemove: () => void
  onAdd: () => void
}) {
  const irrigationFuel = kind === 'irrigation' && variant !== 'equipment'
  const irrigationEquipment = kind === 'irrigation' && variant === 'equipment'
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border p-3 sm:flex-row sm:flex-wrap sm:items-end">
      {irrigationFuel ? (
        <>
          <LineField label="Količina nafte">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.001" min="0" placeholder="0" {...register(`line_items.${index}.quantity`)} />
              <span className="text-xs text-muted-foreground">L</span>
            </div>
          </LineField>
          <LineField label="Ukupna cena">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" min="0" placeholder="0.00" {...register(`line_items.${index}.amount`)} />
              <span className="text-xs text-muted-foreground">EUR</span>
            </div>
          </LineField>
        </>
      ) : null}
      {irrigationEquipment ? (
        <>
          <LineField label="Naziv opreme" className="min-w-0 flex-1 basis-40">
            <Input placeholder="Naziv opreme" {...register(`line_items.${index}.name`)} />
          </LineField>
          <LineField label="Količina" className="sm:w-56">
            <div className="flex gap-2">
              <Input type="number" step="0.001" min="0" placeholder="0" className="min-w-0 flex-1" {...register(`line_items.${index}.quantity`)} />
              <Select className="w-24 flex-none" {...register(`line_items.${index}.unit`)}>
                <option value="kom">kom</option>
                <option value="sati">sati</option>
                <option value="m">m</option>
                <option value="L">L</option>
              </Select>
            </div>
          </LineField>
          <LineField label="Ukupna cena" className="sm:w-36">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" min="0" placeholder="0.00" {...register(`line_items.${index}.amount`)} />
              <span className="text-xs text-muted-foreground">EUR</span>
            </div>
          </LineField>
        </>
      ) : null}
      {kind === 'spraying' ? (
        <>
          <LineField label="Preparat" className="min-w-0 flex-1 basis-40">
            <Input placeholder="Naziv preparata" {...register(`line_items.${index}.name`)} />
          </LineField>
          <LineField label="Litraža / težina" className="sm:w-56">
            <div className="flex gap-2">
              <Input type="number" step="0.001" min="0" placeholder="0" className="min-w-0 flex-1" {...register(`line_items.${index}.quantity`)} />
              <Select className="w-20 flex-none" {...register(`line_items.${index}.unit`)}>
                <option value="L">L</option>
                <option value="kg">kg</option>
              </Select>
            </div>
          </LineField>
          <LineField label="Ukupna cena" className="sm:w-36">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" min="0" placeholder="0.00" {...register(`line_items.${index}.amount`)} />
              <span className="text-xs text-muted-foreground">EUR</span>
            </div>
          </LineField>
        </>
      ) : null}
      {kind === 'fertilization' ? (
        <>
          <LineField label="Preparat" className="min-w-0 flex-1 basis-40">
            <Input placeholder="Naziv preparata" {...register(`line_items.${index}.name`)} />
          </LineField>
          <LineField label="Težina" className="sm:w-36">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.001" min="0" placeholder="0" {...register(`line_items.${index}.quantity`)} />
              <span className="text-xs text-muted-foreground">kg</span>
            </div>
          </LineField>
          <LineField label="Ukupna cena" className="sm:w-36">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" min="0" placeholder="0.00" {...register(`line_items.${index}.amount`)} />
              <span className="text-xs text-muted-foreground">EUR</span>
            </div>
          </LineField>
        </>
      ) : null}
      {kind === 'other' ? (
        <>
          <LineField label="Naziv" className="min-w-0 flex-1 basis-40">
            <Input placeholder="Naziv stavke" {...register(`line_items.${index}.name`)} />
          </LineField>
          <LineField label="Količina" className="sm:w-56">
            <div className="flex gap-2">
              <Input type="number" step="0.001" min="0" placeholder="0" className="min-w-0 flex-1" {...register(`line_items.${index}.quantity`)} />
              <Select className="w-24 flex-none" {...register(`line_items.${index}.unit`)}>
                <option value="">jed.</option>
                <option value="kg">kg</option>
                <option value="L">L</option>
                <option value="m³">m³</option>
                <option value="sati">sati</option>
                <option value="kom">kom</option>
              </Select>
            </div>
          </LineField>
          <LineField label="Cena" className="sm:w-36">
            <div className="flex items-center gap-2">
              <Input type="number" step="0.01" min="0" placeholder="0.00" {...register(`line_items.${index}.amount`)} />
              <span className="text-xs text-muted-foreground">EUR</span>
            </div>
          </LineField>
        </>
      ) : null}
      {canRemove || isLast ? (
        <div className="flex items-center gap-2 sm:pb-0.5">
          {canRemove ? (
            <Button type="button" variant="ghost" size="sm" aria-label="Ukloni stavku" onClick={onRemove}>
              <X className="h-4 w-4" />
            </Button>
          ) : null}
          {isLast ? (
            <Button type="button" variant="outline" size="sm" aria-label="Dodaj stavku" onClick={onAdd}>
              <Plus className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function LineField({
  label,
  className,
  children,
}: {
  label: string
  className?: string
  children: ReactNode
}) {
  return (
    <div className={`min-w-0 flex-1 space-y-1 ${className ?? ''}`}>
      <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
      {children}
    </div>
  )
}

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  )
}
