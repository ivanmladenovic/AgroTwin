import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { addObservation, getDiseaseCase, updateDiseaseCase, uploadPhoto } from '@/features/health/cases'
import { DiseaseAnalysisPanel } from '@/features/health/DiseaseAnalysisPanel'
import { categoryLabel, diseaseStatuses, severityLabel, statusLabel } from '@/features/health/labels'
import { PhotoGallery } from '@/features/health/PhotoGallery'
import { PhotoPicker } from '@/features/health/PhotoPicker'
import { formatDate } from '@/shared/lib/format'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function DiseaseDetailPage() {
  const { caseId } = useParams()
  const [params] = useSearchParams()
  const returnTo = params.get('returnTo') || '/health'
  const queryClient = useQueryClient()
  const caseQuery = useQuery({
    queryKey: ['disease-case', caseId],
    queryFn: () => getDiseaseCase(caseId!),
    enabled: Boolean(caseId),
  })
  const item = caseQuery.data
  const updateMutation = useMutation({
    mutationFn: (status: 'open' | 'monitoring' | 'resolved' | 'unknown') => updateDiseaseCase(caseId!, { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['disease-case', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['disease-cases'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin'] })
      await queryClient.invalidateQueries({ queryKey: ['tree-journal'] })
    },
  })

  if (caseQuery.isLoading) return <p className="text-sm text-muted-foreground">Učitavanje opažanja…</p>
  if (!item) return <p className="text-sm text-danger">Opažanje nije pronađeno.</p>

  const treeHref = item.tree_id
    ? `/orchard/${item.parcel_id}/trees/${item.tree_id}`
    : `/orchard/${item.parcel_id}`

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kicker">
            {categoryLabel(item.category)}
          </p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">{item.title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {item.tree_public_id ?? item.parcel_name} · {formatDate(item.detected_on)} · {severityLabel(item.severity)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={treeHref}>
            <Button variant="outline" size="sm">
              {item.tree_public_id ? 'Otvori stablo' : 'Otvori parcelu'}
            </Button>
          </Link>
          <BackButton fallback={returnTo} />
        </div>
      </div>

      <p className="border border-border bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
        Ovo je terensko opažanje. AgroTwin ne potvrđuje dijagnozu bolesti, štetočine ili nedostatka hraniva.
      </p>

      <div className="grid gap-4 md:grid-cols-3">
        <Fact label="Status" value={statusLabel(item.status)} />
        <Fact label="Ozbiljnost" value={severityLabel(item.severity)} />
        <Fact label="Zahvaćeno stablo" value={item.tree_public_id ?? 'Grupa / parcela'} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Status</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {diseaseStatuses.map((status) => (
            <Button
              key={status.value}
              size="sm"
              variant={item.status === status.value ? 'default' : 'outline'}
              onClick={() => updateMutation.mutate(status.value)}
              disabled={updateMutation.isPending}
            >
              {status.label}
            </Button>
          ))}
        </CardContent>
      </Card>

      {item.description || item.notes ? (
        <Card>
          <CardHeader>
            <CardTitle>Beleške</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {item.description ? <p>{item.description}</p> : null}
            {item.notes ? <p className="text-muted-foreground">{item.notes}</p> : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Hronologija</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <TimelineLine date={item.detected_on} title="Problem je zabeležen" body={item.title} />
          {[...item.observations]
            .sort((a, b) => a.observed_on.localeCompare(b.observed_on))
            .map((observation) => (
              <TimelineLine
                key={observation.id}
                date={observation.observed_on}
                title="Opažanje"
                body={observation.symptoms || observation.notes || 'Simptomi nisu navedeni'}
              />
            ))}
          {item.resolved_on ? <TimelineLine date={item.resolved_on} title="Označeno kao rešeno" /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Opažanja</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {item.observations.length === 0 ? (
            <p className="text-sm text-muted-foreground">Još nema naknadnih opažanja.</p>
          ) : (
            item.observations.map((observation) => (
              <div key={observation.id} className="space-y-2 border-b border-border pb-4 last:border-0">
                <p className="font-mono text-xs text-muted-foreground">{formatDate(observation.observed_on)}</p>
                {observation.symptoms ? <p className="text-sm">{observation.symptoms}</p> : null}
                {observation.notes ? <p className="text-sm text-muted-foreground">{observation.notes}</p> : null}
                {observation.photos.length > 0 ? <PhotoGallery photos={observation.photos} /> : null}
              </div>
            ))
          )}
          <AddObservationForm caseId={item.id} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Fotografije</CardTitle>
        </CardHeader>
        <CardContent>
          <PhotoGallery photos={item.photos} />
        </CardContent>
      </Card>

      <DiseaseAnalysisPanel caseId={item.id} photos={item.photos} />
    </div>
  )
}

function AddObservationForm({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [observedOn, setObservedOn] = useState(new Date().toISOString().slice(0, 10))
  const [symptoms, setSymptoms] = useState('')
  const [notes, setNotes] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const mutation = useMutation({
    mutationFn: async () => {
      const observation = await addObservation(caseId, {
        observed_on: observedOn,
        symptoms: symptoms || null,
        notes: notes || null,
      })
      for (const file of files) {
        await uploadPhoto(file, 'observation', observation.id)
      }
      return observation
    },
    onSuccess: async () => {
      setSymptoms('')
      setNotes('')
      setFiles([])
      await queryClient.invalidateQueries({ queryKey: ['disease-case', caseId] })
      await queryClient.invalidateQueries({ queryKey: ['tree-journal'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin'] })
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }

  return (
    <form className="space-y-3 border border-border p-4" onSubmit={onSubmit}>
      <p className="text-sm font-medium">Dodaj opažanje</p>
      <div className="space-y-1.5">
        <Label>Datum</Label>
        <Input type="date" value={observedOn} onChange={(event) => setObservedOn(event.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label>Fotografije</Label>
        <PhotoPicker files={files} onChange={setFiles} />
      </div>
      <div className="space-y-1.5">
        <Label>Simptomi</Label>
        <Textarea rows={3} value={symptoms} onChange={(event) => setSymptoms(event.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label>Beleške</Label>
        <Textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </div>
      <Button type="submit" size="sm" disabled={mutation.isPending}>
        {mutation.isPending ? 'Čuvanje…' : 'Sačuvaj opažanje'}
      </Button>
    </form>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent className="text-lg font-medium">{value}</CardContent>
    </Card>
  )
}

function TimelineLine({ date, title, body }: { date: string; title: string; body?: string }) {
  return (
    <div>
      <p className="font-mono text-xs text-muted-foreground">{formatDate(date)}</p>
      <p className="mt-1 text-sm font-medium">{title}</p>
      {body ? <p className="text-sm text-muted-foreground">{body}</p> : null}
    </div>
  )
}
