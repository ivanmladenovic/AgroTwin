import { useEffect, useRef, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { MapPinned, Plus, X } from 'lucide-react'
import { useFieldArray, useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'

import { createActivity, listActivityTypes } from '@/features/journal/api'
import { defaultActivityStatus } from '@/features/journal/labels'
import { OrchardPickerDialog } from '@/features/journal/OrchardPickerDialog'
import { activityFormSchema, type ActivityFormValues } from '@/features/journal/schemas'
import { todayKey } from '@/features/journal/calendar'
import { listParcelRows, listParcels, listParcelTrees } from '@/features/orchard/api'
import type { ActivityScope, ActivityStatus } from '@/shared/api/types'
import { isEurUnit, rowLabel } from '@/shared/lib/format'
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
      line_items: [{ quantity: '', unit: '' }],
    },
  })

  const items = useFieldArray({ control: form.control, name: 'line_items' })
  const lineItems = form.watch('line_items')
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

  useEffect(() => {
    if (typesQuery.data?.[0] && !form.getValues('activity_type_id')) {
      form.setValue('activity_type_id', typesQuery.data[0].id)
    }
  }, [form, typesQuery.data])

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
    mutationFn: createActivity,
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
        const lineItems = values.line_items
          .map((item) => ({
            quantity: item.quantity?.trim() ? Number(item.quantity) : null,
            unit: item.unit?.trim() || null,
          }))
          .filter((item) => item.quantity != null || item.unit)
        const first = lineItems[0]
        mutation.mutate({
          activity_type_id: values.activity_type_id,
          performed_on: values.performed_on,
          scope_type: values.scope_type,
          parcel_id: values.parcel_id,
          row_id: values.scope_type === 'parcel' ? null : values.row_id || values.row_ids[0] || null,
          row_ids: values.scope_type === 'row' ? values.row_ids : [],
          tree_id: values.scope_type === 'tree' ? values.tree_id || null : null,
          description: values.description || null,
          quantity: first?.quantity != null && !Number.isNaN(first.quantity) ? first.quantity : null,
          unit: first?.unit || null,
          line_items: lineItems.map((item) => ({
            quantity: item.quantity != null && !Number.isNaN(item.quantity) ? item.quantity : null,
            unit: item.unit,
          })),
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
          <Select {...form.register('scope_type')}>
            <option value="parcel">Parcela</option>
            <option value="row">Red</option>
            <option value="tree">Stablo</option>
          </Select>
        </Field>
      </div>

      {parcelName ? <p className="text-sm text-muted-foreground">Zasad: {parcelName}</p> : null}

      {scope === 'row' ? (
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

      {scope === 'tree' ? (
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

      <div className="space-y-2">
        <Label>Količina i jedinica</Label>
        {items.fields.map((field, index) => {
          const eur = isEurUnit(lineItems[index]?.unit)
          return (
            <div key={field.id} className="flex flex-wrap items-center gap-2">
              <Input
                type="number"
                step={eur ? '0.01' : '0.001'}
                min="0"
                placeholder={eur ? 'Iznos' : 'Količina'}
                className="min-w-0 flex-1 basis-28"
                {...form.register(`line_items.${index}.quantity`)}
              />
              <Input
                list="activity-units"
                placeholder="EUR, L, kg, m³, sati"
                className="min-w-0 w-full flex-1 basis-28 sm:w-36 sm:flex-none"
                {...form.register(`line_items.${index}.unit`)}
              />
              {items.fields.length > 1 ? (
                <Button type="button" variant="ghost" size="sm" aria-label="Ukloni stavku" onClick={() => items.remove(index)}>
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
              {index === items.fields.length - 1 ? (
                <Button type="button" variant="outline" size="sm" aria-label="Dodaj stavku" onClick={() => items.append({ quantity: '', unit: '' })}>
                  <Plus className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          )
        })}
        <datalist id="activity-units">
          <option value="EUR" />
          <option value="L" />
          <option value="kg" />
          <option value="m³" />
          <option value="sati" />
        </datalist>
      </div>

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
        <Link to={prefill.return_to || '/journal'} className="text-sm text-muted-foreground hover:text-foreground">
          Otkaži
        </Link>
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
