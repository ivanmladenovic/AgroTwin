import { MapPinned } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { createConversation } from '@/features/agronomist/api'
import { saveReportedProblem } from '@/features/health/cases'
import { categoryLabel, diseaseCategories, diseaseSeverities, diseaseStatuses, severityLabel } from '@/features/health/labels'
import { PhotoPicker } from '@/features/health/PhotoPicker'
import { reportProblemSchema, type ReportProblemValues } from '@/features/health/schemas'
import { OrchardPickerDialog } from '@/features/journal/OrchardPickerDialog'
import { listParcelRows, listParcels, listParcelTrees } from '@/features/orchard/api'
import { rowLabel } from '@/shared/lib/format'
import { BackLink } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function ReportProblemForm({
  variant = 'health',
  onCancel,
}: {
  variant?: 'health' | 'agronomist'
  onCancel?: () => void
}) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const returnTo = params.get('returnTo') || (variant === 'agronomist' ? '/agronomist' : '/health')
  const [files, setFiles] = useState<File[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)
  const [photoError, setPhotoError] = useState<string | null>(null)
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const defaultScope = params.get('treeId') ? 'tree' : params.get('rowId') ? 'row' : 'tree'
  const form = useForm<ReportProblemValues>({
    resolver: zodResolver(reportProblemSchema),
    defaultValues: {
      title: '',
      category: 'unknown',
      severity: 'medium',
      status: 'open',
      detected_on: new Date().toISOString().slice(0, 10),
      parcel_id: params.get('parcelId') ?? '',
      scope: defaultScope,
      row_id: params.get('rowId') ?? '',
      tree_id: params.get('treeId') ?? '',
      tree_ids: params.get('treeId') ? [params.get('treeId') as string] : [],
      description: '',
      symptoms: '',
      notes: '',
    },
  })
  const parcelId = form.watch('parcel_id') || params.get('parcelId') || ''
  const rowId = form.watch('row_id') || params.get('rowId') || ''
  const scope = form.watch('scope')
  const treeIds = form.watch('tree_ids') ?? []
  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
    enabled: Boolean(parcelId),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId, scope === 'trees' ? null : rowId],
    queryFn: () => listParcelTrees(parcelId, scope === 'trees' ? undefined : rowId || undefined),
    enabled: Boolean(parcelId && (scope === 'trees' || rowId)),
  })

  useEffect(() => {
    const parcels = parcelsQuery.data ?? []
    const prefill = params.get('parcelId')
    if (prefill && parcels.some((parcel) => parcel.id === prefill)) {
      form.setValue('parcel_id', prefill)
      return
    }
    if (!prefill && parcels[0] && !form.getValues('parcel_id')) {
      form.setValue('parcel_id', parcels[0].id)
    }
  }, [form, params, parcelsQuery.data])

  useEffect(() => {
    const prefill = params.get('rowId')
    if (prefill && (rowsQuery.data ?? []).some((row) => row.id === prefill)) {
      form.setValue('row_id', prefill)
    }
  }, [form, params, rowsQuery.data])

  useEffect(() => {
    const prefill = params.get('treeId')
    if (prefill && (treesQuery.data ?? []).some((tree) => tree.id === prefill)) {
      form.setValue('tree_id', prefill)
      form.setValue('tree_ids', [prefill])
    }
  }, [form, params, treesQuery.data])

  const mutation = useMutation({
    mutationFn: async ({ values, sendToAgronomist }: { values: ReportProblemValues; sendToAgronomist: boolean }) => {
      if (sendToAgronomist && files.length === 0) {
        throw new Error('Dodajte bar jednu fotografiju pre slanja agronomu.')
      }
      const created = await saveReportedProblem(values, files)
      if (!sendToAgronomist) return { created, conversationId: null as string | null }
      const conversation = await createConversation(values.title, {
        parcel_id: created.parcel_id,
        disease_case_id: created.id,
      })
      return { created, conversationId: conversation.id, values }
    },
    onSuccess: (result, variables) => {
      if (variables.sendToAgronomist && result.conversationId) {
        const parcelName = (parcelsQuery.data ?? []).find((item) => item.id === variables.values.parcel_id)?.name
        const rowName = (rowsQuery.data ?? []).find((item) => item.id === variables.values.row_id)
        const treeLabels = (treesQuery.data ?? [])
          .filter((tree) => (variables.values.tree_ids ?? []).includes(tree.id) || tree.id === variables.values.tree_id)
          .map((tree) => tree.public_id)
        void navigate(`/agronomist/${result.conversationId}`, {
          replace: variant === 'agronomist',
          state: {
            initialMessage: formatProblemChatMessage(variables.values, {
              parcelName,
              rowName: rowName ? rowLabel(rowName.row_number) : undefined,
              treeLabels,
              photoCount: files.length,
            }),
          },
        })
        return
      }
      const destination = params.get('returnTo')
      void navigate(destination || `/health/${result.created.id}`)
    },
  })

  const selectedTrees = (treesQuery.data ?? []).filter((tree) => treeIds.includes(tree.id) || tree.id === form.watch('tree_id'))
  const selectedRow = (rowsQuery.data ?? []).find((row) => row.id === rowId)

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit((values) => {
        setPhotoError(null)
        mutation.mutate({ values, sendToAgronomist: false })
      })}
    >
      <Field label="Naslov" error={form.formState.errors.title?.message}>
        <Input {...form.register('title')} />
      </Field>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Kategorija">
          <Select {...form.register('category')}>
            {diseaseCategories.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Ozbiljnost">
          <Select {...form.register('severity')}>
            {diseaseSeverities.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Status">
          <Select {...form.register('status')}>
            {diseaseStatuses.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Datum uočavanja">
          <Input type="date" {...form.register('detected_on')} />
        </Field>
        <Field label="Parcela" error={form.formState.errors.parcel_id?.message}>
          <Select {...form.register('parcel_id')}>
            <option value="">Izaberite parcelu</option>
            {(parcelsQuery.data ?? []).map((parcel) => (
              <option key={parcel.id} value={parcel.id}>
                {parcel.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Obuhvat">
          <Select
            {...form.register('scope')}
            onChange={(event) => {
              const next = event.target.value as ReportProblemValues['scope']
              form.setValue('scope', next)
              if (next === 'row') {
                form.setValue('tree_id', '')
                form.setValue('tree_ids', [])
              }
              if (next === 'tree') {
                form.setValue('tree_ids', form.getValues('tree_id') ? [form.getValues('tree_id') as string] : [])
              }
            }}
          >
            <option value="tree">Jedna sadnica</option>
            <option value="trees">Više sadnica</option>
            <option value="row">Ceo red</option>
          </Select>
        </Field>
        <Field label={scope === 'trees' ? 'Red (opciono)' : 'Red'} error={form.formState.errors.row_id?.message}>
          <Select
            {...form.register('row_id')}
            onChange={(event) => {
              form.setValue('row_id', event.target.value)
              form.setValue('tree_id', '')
              form.setValue('tree_ids', [])
            }}
          >
            <option value="">{scope === 'trees' ? 'Svi redovi' : 'Izaberite red'}</option>
            {(rowsQuery.data ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {row.name ?? rowLabel(row.row_number)}
              </option>
            ))}
          </Select>
        </Field>
        {scope === 'tree' ? (
          <Field label="Sadnica" error={form.formState.errors.tree_id?.message}>
            <Select
              {...form.register('tree_id')}
              disabled={!rowId}
              onChange={(event) => {
                form.setValue('tree_id', event.target.value)
                form.setValue('tree_ids', event.target.value ? [event.target.value] : [])
              }}
            >
              <option value="">Izaberite sadnicu</option>
              {(treesQuery.data ?? []).map((tree) => (
                <option key={tree.id} value={tree.id}>
                  {tree.public_id}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}
        <div className="md:col-span-2">
          <Field label={scope === 'row' ? 'Red na mapi' : 'Sadnice na mapi'} error={form.formState.errors.tree_ids?.message}>
            <div className="space-y-2">
              <Button type="button" variant="outline" size="sm" disabled={!parcelId} onClick={() => setPickerOpen(true)}>
                <MapPinned className="h-4 w-4" />
                Označi na mapi
              </Button>
              <p className="text-xs text-muted-foreground">
                {scope === 'row'
                  ? selectedRow
                    ? `Izabran red: ${selectedRow.name ?? rowLabel(selectedRow.row_number)}`
                    : 'Nijedan red nije izabran'
                  : selectedTrees.length
                    ? `Izabrano: ${selectedTrees.map((tree) => tree.public_id).join(', ')}`
                    : 'Nijedna sadnica nije izabrana'}
              </p>
            </div>
          </Field>
        </div>
      </div>
      <Field label="Opis">
        <Textarea rows={3} {...form.register('description')} />
      </Field>
      <Field label="Početni simptomi">
        <Textarea rows={3} {...form.register('symptoms')} />
      </Field>
      <Field label="Beleške">
        <Textarea rows={3} {...form.register('notes')} />
      </Field>
      <Field label="Fotografije">
        <PhotoPicker
          files={files}
          onChange={setFiles}
          description={
            variant === 'agronomist'
              ? 'Uslikajte simptom ili dodajte fotografije iz galerije. Za slanje agronomu potrebna je bar jedna fotografija.'
              : undefined
          }
        />
        {photoError ? <p className="text-xs text-danger">{photoError}</p> : null}
      </Field>
      {mutation.isError ? (
        <p className="text-sm text-danger">{mutation.error instanceof Error ? mutation.error.message : 'Čuvanje nije uspelo'}</p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          variant={variant === 'agronomist' ? 'outline' : 'default'}
          disabled={mutation.isPending}
        >
          {mutation.isPending && !mutation.variables?.sendToAgronomist ? 'Čuvanje…' : 'Sačuvaj opažanje'}
        </Button>
        <Button
          type="button"
          disabled={mutation.isPending}
          onClick={() => {
            if (files.length === 0) {
              setPhotoError('Uslikajte ili izaberite bar jednu fotografiju.')
              return
            }
            setPhotoError(null)
            void form.handleSubmit((values) => mutation.mutate({ values, sendToAgronomist: true }))()
          }}
        >
          {mutation.isPending && mutation.variables?.sendToAgronomist ? 'Slanje agronomu…' : 'Pošalji agronomu'}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" disabled={mutation.isPending} onClick={onCancel}>
            Otkaži
          </Button>
        ) : (
          <BackLink fallback={returnTo}>Otkaži</BackLink>
        )}
      </div>
      {pickerOpen && parcelId ? (
        <OrchardPickerDialog
          parcelId={parcelId}
          mode={scope === 'row' ? 'rows' : scope === 'trees' ? 'trees' : 'tree'}
          selectedRowIds={rowId ? [rowId] : []}
          selectedTreeId={form.watch('tree_id') || null}
          selectedTreeIds={scope === 'tree' && form.watch('tree_id') ? [form.watch('tree_id') as string] : treeIds}
          onToggleRow={(id) => {
            if (scope !== 'row') return
            form.setValue('row_id', id === form.getValues('row_id') ? '' : id, { shouldValidate: true })
            form.setValue('tree_id', '')
            form.setValue('tree_ids', [])
          }}
          onSelectTree={(treeId, treeRowId) => {
            if (scope === 'tree') {
              form.setValue('tree_id', treeId, { shouldValidate: true })
              form.setValue('tree_ids', [treeId])
              form.setValue('row_id', treeRowId)
              return
            }
            if (scope !== 'trees') return
            const current = form.getValues('tree_ids') ?? []
            const next = current.includes(treeId) ? current.filter((id) => id !== treeId) : [...current, treeId]
            form.setValue('tree_ids', next, { shouldValidate: true })
            const selected = (treesQuery.data ?? []).filter((tree) => next.includes(tree.id))
            const rowIds = new Set(selected.map((tree) => tree.row_id))
            if (rowIds.size === 1) form.setValue('row_id', [...rowIds][0])
            else if (rowIds.size > 1) form.setValue('row_id', '')
            else form.setValue('row_id', treeRowId)
          }}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
    </form>
  )
}

function formatProblemChatMessage(
  values: ReportProblemValues,
  options: { parcelName?: string; rowName?: string; treeLabels: string[]; photoCount: number },
) {
  const scopeLine =
    values.scope === 'row'
      ? `Ceo red: ${options.rowName || 'red'}`
      : options.treeLabels.length
        ? `Sadnice: ${options.treeLabels.join(', ')}`
        : 'Lokacija nije precizirana'
  return [
    `Prijavljen je problem: ${values.title}.`,
    `Parcela: ${options.parcelName || '-'}`,
    scopeLine,
    `Kategorija: ${categoryLabel(values.category)}`,
    `Ozbiljnost: ${severityLabel(values.severity)}`,
    `Datum: ${values.detected_on}`,
    values.description ? `Opis: ${values.description}` : null,
    values.symptoms ? `Simptomi: ${values.symptoms}` : null,
    values.notes ? `Beleške: ${values.notes}` : null,
    options.photoCount ? `Priloženo fotografija: ${options.photoCount}.` : 'Nema priloženih fotografija.',
    'Pregledajte opažanje i predložite sledeći korak. Ovo nije zahtev za potvrđenu dijagnozu.',
  ]
    .filter(Boolean)
    .join('\n')
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
