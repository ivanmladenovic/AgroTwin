import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { uploadPhoto } from '@/features/health/cases'
import { PhotoPicker } from '@/features/health/PhotoPicker'
import { listParcelRows, listParcelTrees } from '@/features/orchard/api'
import { createHarvest, updateHarvest } from '@/features/production/api'
import { harvestQualityOptions } from '@/features/production/labels'
import { harvestFormSchema, type HarvestFormValues } from '@/features/production/schemas'
import { todayKey } from '@/features/journal/calendar'
import type { HarvestEvent, HarvestEventPayload, HarvestScope } from '@/shared/api/types'
import { formatKg, rowLabel } from '@/shared/lib/format'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'
import { tr } from '@/shared/i18n/i18n'

function useHarvestScopes() {
  const { i18n } = useTranslation()
  void i18n.language
  return useMemo(
    (): Array<{ value: HarvestScope; label: string; hint: string }> => [
      { value: 'parcel', label: tr('Cela parcela'), hint: tr('Ukupan urod parcele') },
      { value: 'row', label: tr('Određeni red'), hint: tr('Merenje jednog reda') },
      { value: 'tree', label: tr('Određeno stablo'), hint: tr('Merenje jednog stabla') },
    ],
    [i18n.language],
  )
}

export function HarvestForm({
  parcelId,
  harvest,
  year,
}: {
  parcelId: string
  harvest?: HarvestEvent
  year?: number
}) {
  const { i18n } = useTranslation()
  void i18n.language
  const scopes = useHarvestScopes()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [files, setFiles] = useState<File[]>([])
  const form = useForm<HarvestFormValues>({
    resolver: zodResolver(harvestFormSchema),
    defaultValues: harvest
      ? valuesFromHarvest(harvest)
      : {
          harvested_on: todayKey(),
          scope_type: 'parcel',
          row_id: '',
          tree_id: '',
          gross_quantity: '',
          loss_quantity: '0',
          unit: 'kg',
          moisture_percent: '',
          quality_category: '',
          damaged_percent: '',
          empty_nuts_percent: '',
          foreign_material_percent: '',
          size_or_caliber: '',
          notes: '',
        },
  })
  const scope = form.watch('scope_type')
  const rowId = form.watch('row_id') || ''
  const gross = form.watch('gross_quantity')
  const loss = form.watch('loss_quantity')
  const previousScope = useRef(scope)
  const net = liveNet(gross, loss)

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

  useEffect(() => {
    if (previousScope.current === scope) return
    previousScope.current = scope
    if (scope === 'parcel') {
      form.setValue('row_id', '')
      form.setValue('tree_id', '')
    }
    if (scope === 'row') form.setValue('tree_id', '')
  }, [form, scope])

  const mutation = useMutation({
    mutationFn: async (values: HarvestFormValues) => {
      const payload = toPayload(values)
      const saved = harvest
        ? await updateHarvest(parcelId, harvest.id, payload)
        : await createHarvest(parcelId, payload)
      for (const file of files) {
        await uploadPhoto(file, 'harvest_event', saved.id)
      }
      return saved
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['parcel-production', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['parcel-report', parcelId] })
      await queryClient.invalidateQueries({ queryKey: ['harvest', parcelId, saved.id] })
      const harvestYear = Number(saved.harvested_on.slice(0, 4))
      void navigate(`/orchard/${parcelId}/production/${saved.id}?year=${harvestYear || year || ''}`)
    },
  })

  return (
    <form className="space-y-6" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={tr('Datum berbe')} error={form.formState.errors.harvested_on?.message}>
          <Input type="date" {...form.register('harvested_on')} />
        </Field>
        <Field label={tr('Jedinica')}>
          <Select {...form.register('unit')}>
            <option value="kg">kg</option>
          </Select>
        </Field>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{tr('Obuhvat')}</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {scopes.map((item) => (
            <label
              key={item.value}
              className={`flex min-h-14 cursor-pointer items-start gap-3 rounded-lg border px-3 py-3 ${
                scope === item.value ? 'border-primary bg-primary/5' : 'border-border'
              }`}
            >
              <input
                type="radio"
                className="mt-1"
                value={item.value}
                checked={scope === item.value}
                onChange={() => form.setValue('scope_type', item.value)}
              />
              <span>
                <span className="block text-sm font-medium">{item.label}</span>
                <span className="block text-xs text-muted-foreground">{item.hint}</span>
              </span>
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {tr(
            'Ukupan prinos parcele računa se samo iz berbi cele parcele. Berbe redova i stabala ostaju posebna merenja.',
          )}
        </p>
      </fieldset>

      {scope === 'row' || scope === 'tree' ? (
        <Field label={tr('Red')} error={form.formState.errors.row_id?.message}>
          <Select {...form.register('row_id')}>
            <option value="">{tr('Izaberite red')}</option>
            {(rowsQuery.data ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {rowLabel(row.row_number)}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}

      {scope === 'tree' ? (
        <Field label={tr('Stablo')} error={form.formState.errors.tree_id?.message}>
          <Select {...form.register('tree_id')} disabled={!rowId}>
            <option value="">{tr('Izaberite stablo')}</option>
            {(treesQuery.data ?? []).map((tree) => (
              <option key={tree.id} value={tree.id}>
                {tree.public_id}
              </option>
            ))}
          </Select>
        </Field>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={tr('Bruto količina')} error={form.formState.errors.gross_quantity?.message}>
          <Input inputMode="decimal" placeholder={tr('npr. 650')} {...form.register('gross_quantity')} />
        </Field>
        <Field label={tr('Gubitak / otpad')} error={form.formState.errors.loss_quantity?.message}>
          <Input inputMode="decimal" placeholder="0" {...form.register('loss_quantity')} />
        </Field>
        <div className="space-y-1.5">
          <Label>{tr('Neto količina')}</Label>
          <div className="flex h-11 items-center rounded-lg border border-border bg-muted px-3 text-base font-semibold lg:h-10 lg:text-sm">
            {net == null ? '—' : formatKg(net)}
          </div>
          <p className="text-xs text-muted-foreground">{tr('Računa se kao bruto minus gubitak.')}</p>
        </div>
      </div>

      <section className="space-y-4 rounded-xl border border-border p-4">
        <div>
          <h2 className="text-sm font-semibold">{tr('Kvalitet')}</h2>
          <p className="text-xs text-muted-foreground">{tr('Opciono. Popunite samo što je izmereno.')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={tr('Vlažnost %')} error={form.formState.errors.moisture_percent?.message}>
            <Input inputMode="decimal" placeholder={tr('npr. 8.5')} {...form.register('moisture_percent')} />
          </Field>
          <Field label={tr('Kategorija kvaliteta')}>
            <Select {...form.register('quality_category')}>
              {harvestQualityOptions().map((item) => (
                <option key={item.value || 'none'} value={item.value}>
                  {item.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={tr('Oštećeni plodovi %')} error={form.formState.errors.damaged_percent?.message}>
            <Input inputMode="decimal" {...form.register('damaged_percent')} />
          </Field>
          <Field label={tr('Prazni plodovi %')} error={form.formState.errors.empty_nuts_percent?.message}>
            <Input inputMode="decimal" {...form.register('empty_nuts_percent')} />
          </Field>
          <Field label={tr('Strane materije %')} error={form.formState.errors.foreign_material_percent?.message}>
            <Input inputMode="decimal" {...form.register('foreign_material_percent')} />
          </Field>
          <Field label={tr('Krupnoća / kalibar')}>
            <Input placeholder={tr('npr. 13-15 mm')} {...form.register('size_or_caliber')} />
          </Field>
        </div>
      </section>

      <Field label={tr('Napomena')}>
        <Textarea rows={3} placeholder={tr('npr. Berba posle tri suva dana.')} {...form.register('notes')} />
      </Field>

      <div className="space-y-2">
        <Label>{tr('Fotografije / dokumentacija')}</Label>
        <PhotoPicker
          files={files}
          onChange={setFiles}
          description={tr('Uslikajte vagu, vreće, izveštaj o kvalitetu ili dokumentaciju berbe.')}
        />
      </div>

      {mutation.error ? (
        <p className="text-sm text-danger">
          {mutation.error instanceof Error ? mutation.error.message : tr('Čuvanje nije uspelo')}
        </p>
      ) : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <BackButton
          fallback={`/orchard/${parcelId}/production${year ? `?year=${year}` : ''}`}
          className="w-full sm:min-w-28"
        >
          {tr('Otkaži')}
        </BackButton>
        <Button type="submit" disabled={mutation.isPending} className="sm:min-w-40">
          {mutation.isPending ? tr('Čuvanje…') : harvest ? tr('Sačuvaj izmene') : tr('Sačuvaj berbu')}
        </Button>
      </div>
    </form>
  )
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  )
}

function liveNet(gross: string, loss?: string) {
  const grossValue = Number((gross || '').replace(',', '.'))
  const lossValue = Number((loss || '0').replace(',', '.'))
  if (!Number.isFinite(grossValue) || !Number.isFinite(lossValue)) return null
  return grossValue - lossValue
}

function optionalNumber(value?: string) {
  if (!value) return null
  const numeric = Number(value.replace(',', '.'))
  return Number.isFinite(numeric) ? numeric : null
}

function toPayload(values: HarvestFormValues): HarvestEventPayload {
  return {
    harvested_on: values.harvested_on,
    scope_type: values.scope_type,
    row_id: values.scope_type === 'parcel' ? null : values.row_id || null,
    tree_id: values.scope_type === 'tree' ? values.tree_id || null : null,
    gross_quantity: Number(values.gross_quantity.replace(',', '.')),
    loss_quantity: Number((values.loss_quantity || '0').replace(',', '.')) || 0,
    unit: values.unit || 'kg',
    moisture_percent: optionalNumber(values.moisture_percent),
    quality_category: values.quality_category ? values.quality_category : null,
    damaged_percent: optionalNumber(values.damaged_percent),
    empty_nuts_percent: optionalNumber(values.empty_nuts_percent),
    foreign_material_percent: optionalNumber(values.foreign_material_percent),
    size_or_caliber: values.size_or_caliber?.trim() || null,
    notes: values.notes?.trim() || null,
  }
}

function valuesFromHarvest(harvest: HarvestEvent): HarvestFormValues {
  return {
    harvested_on: harvest.harvested_on,
    scope_type: harvest.scope_type,
    row_id: harvest.row_id ?? '',
    tree_id: harvest.tree_id ?? '',
    gross_quantity: harvest.gross_quantity ?? '',
    loss_quantity: harvest.loss_quantity,
    unit: harvest.unit || 'kg',
    moisture_percent: harvest.moisture_percent ?? '',
    quality_category: harvest.quality_category ?? '',
    damaged_percent: harvest.damaged_percent ?? '',
    empty_nuts_percent: harvest.empty_nuts_percent ?? '',
    foreign_material_percent: harvest.foreign_material_percent ?? '',
    size_or_caliber: harvest.size_or_caliber ?? '',
    notes: harvest.notes ?? '',
  }
}
