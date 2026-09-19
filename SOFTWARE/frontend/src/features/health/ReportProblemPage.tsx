import { useEffect, useState, type ReactNode } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { createDiseaseCase, getDiseaseCase, uploadPhoto } from '@/features/health/cases'
import { requestDiseaseAnalysis } from '@/features/agronomist/api'
import { diseaseCategories, diseaseSeverities, diseaseStatuses } from '@/features/health/labels'
import { PhotoPicker } from '@/features/health/PhotoPicker'
import { reportProblemSchema, type ReportProblemValues } from '@/features/health/schemas'
import { listParcelRows, listParcels, listParcelTrees } from '@/features/orchard/api'
import { rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function ReportProblemPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [files, setFiles] = useState<File[]>([])
  const [requestAi, setRequestAi] = useState(false)
  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const form = useForm<ReportProblemValues>({
    resolver: zodResolver(reportProblemSchema),
    defaultValues: {
      title: '',
      category: 'unknown',
      severity: 'medium',
      status: 'open',
      detected_on: new Date().toISOString().slice(0, 10),
      parcel_id: params.get('parcelId') ?? '',
      row_id: params.get('rowId') ?? '',
      tree_id: params.get('treeId') ?? '',
      description: '',
      symptoms: '',
      notes: '',
    },
  })
  const parcelId = form.watch('parcel_id') || params.get('parcelId') || ''
  const rowId = form.watch('row_id') || params.get('rowId') || ''
  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
    enabled: Boolean(parcelId),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId, rowId],
    queryFn: () => listParcelTrees(parcelId, rowId),
    enabled: Boolean(parcelId && rowId),
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
    }
  }, [form, params, treesQuery.data])

  const mutation = useMutation({
    mutationFn: async (values: ReportProblemValues) => {
      const created = await createDiseaseCase({
        ...values,
        row_id: values.row_id || null,
        tree_id: values.tree_id || null,
        description: values.description || null,
        symptoms: values.symptoms || (files.length ? 'Uz prijavu je priložena fotografija.' : null),
        notes: values.notes || null,
      })
      const detail = await getDiseaseCase(created.id)
      const observationId = detail.observations[0]?.id
      if (observationId) {
        for (const file of files) {
          await uploadPhoto(file, 'observation', observationId)
        }
      }
      if (requestAi) {
        await requestDiseaseAnalysis(created.id, { notes: values.symptoms || values.notes || null })
      }
      return created
    },
    onSuccess: (item) => {
      const returnTo = params.get('returnTo')
      void navigate(returnTo || `/health/${item.id}`)
    },
  })

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Zdravlje stabala</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Prijavi problem</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Zabeležite simptome i beleške. Ovo nije medicinska ni agronomska dijagnoza.
        </p>
      </div>
      <form
        className="space-y-4 rounded-xl border border-border bg-card p-4 sm:p-6"
        onSubmit={form.handleSubmit((values) => {
          mutation.mutate(values)
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
          <Field label="Red">
            <Select {...form.register('row_id')}>
              <option value="">Cela parcela / kasnije</option>
              {(rowsQuery.data ?? []).map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name ?? rowLabel(row.row_number)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Stablo">
            <Select {...form.register('tree_id')} disabled={!rowId}>
              <option value="">Grupa stabala / kasnije</option>
              {(treesQuery.data ?? []).map((tree) => (
                <option key={tree.id} value={tree.id}>
                  {tree.public_id}
                </option>
              ))}
            </Select>
          </Field>
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
          <PhotoPicker files={files} onChange={setFiles} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={requestAi} onChange={(event) => setRequestAi(event.target.checked)} />
          Zatraži AI čitanje posle čuvanja (nije dijagnoza)
        </label>
        {mutation.isError ? (
          <p className="text-sm text-danger">{mutation.error instanceof Error ? mutation.error.message : 'Čuvanje nije uspelo'}</p>
        ) : null}
        <div className="flex gap-3">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Čuvanje…' : 'Sačuvaj opažanje'}
          </Button>
          <Link to="/health" className="text-sm text-muted-foreground hover:text-foreground">
            Otkaži
          </Link>
        </div>
      </form>
    </div>
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
