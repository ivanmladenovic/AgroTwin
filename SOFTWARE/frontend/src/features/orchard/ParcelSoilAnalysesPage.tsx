import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, FileText, MapPinned, Plus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { todayKey } from '@/features/journal/calendar'
import {
  downloadSoilAnalysis,
  listParcelSoilAnalyses,
  openSoilAnalysis,
  uploadParcelSoilAnalysis,
} from '@/features/journal/api'
import { OrchardPickerDialog } from '@/features/journal/OrchardPickerDialog'
import { getParcel, listParcelRows, listParcelTrees } from '@/features/orchard/api'
import type { SoilLabAnalysis } from '@/shared/api/types'
import { formatDate, rowLabel } from '@/shared/lib/format'
import { BackButton } from '@/shared/ui/back-button'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

export function ParcelSoilAnalysesPage() {
  const { parcelId } = useParams()
  const queryClient = useQueryClient()
  const [adding, setAdding] = useState(false)
  const parcelQuery = useQuery({
    queryKey: ['parcel', parcelId],
    queryFn: () => getParcel(parcelId!),
    enabled: Boolean(parcelId),
  })
  const analysesQuery = useQuery({
    queryKey: ['parcel-soil-analyses', parcelId],
    queryFn: () => listParcelSoilAnalyses(parcelId!),
    enabled: Boolean(parcelId),
  })

  if (!parcelId) return null

  const mapHref = `/orchard/${parcelId}`
  const analyses = analysesQuery.data ?? []

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kicker">Zemljište</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Analize zemljišta</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {parcelQuery.data?.name ?? 'Parcela'} · PDF laboratorijskih analiza i najbliža sadnica uzorka
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <BackButton fallback={mapHref}>Nazad na mapu</BackButton>
          <Button type="button" size="sm" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" />
            Nova analiza
          </Button>
        </div>
      </div>

      {adding ? (
        <AddSoilAnalysisForm
          parcelId={parcelId}
          onClose={() => setAdding(false)}
          onSaved={async () => {
            setAdding(false)
            await queryClient.invalidateQueries({ queryKey: ['parcel-soil-analyses', parcelId] })
            await queryClient.invalidateQueries({ queryKey: ['activities'] })
          }}
        />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Sačuvane analize</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {analysesQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Učitavanje analiza…</p>
          ) : analyses.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Još nema analiza. Dodajte PDF i povežite ga sa najbližom sadnicom gde je uzet uzorak.
            </p>
          ) : (
            analyses.map((analysis) => <AnalysisRow key={analysis.id} analysis={analysis} parcelId={parcelId} />)
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function AnalysisRow({ analysis, parcelId }: { analysis: SoilLabAnalysis; parcelId: string }) {
  const [opening, setOpening] = useState(false)
  const treeHref = `/orchard/${parcelId}?tree=${analysis.tree_id}`

  async function handleOpen() {
    setOpening(true)
    try {
      const opened = await openSoilAnalysis(analysis)
      if (!opened) await downloadSoilAnalysis(analysis)
    } finally {
      setOpening(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-background px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{analysis.original_filename}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {formatDate(analysis.sampled_on)}
          {analysis.row_number != null ? ` · ${rowLabel(analysis.row_number)}` : ''}
          {analysis.tree_public_id ? ` · ${analysis.tree_public_id}` : ''}
        </p>
        {analysis.tree_id ? (
          <Link to={treeHref} className="mt-1 inline-flex text-xs font-medium text-primary hover:underline">
            Prikaži sadnicu na mapi
          </Link>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline" disabled={opening} onClick={() => void handleOpen()}>
          <Eye className="h-4 w-4" />
          {opening ? 'Otvaranje…' : 'Otvori'}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => void downloadSoilAnalysis(analysis)}>
          <Download className="h-4 w-4" />
          Preuzmi
        </Button>
      </div>
    </div>
  )
}

function AddSoilAnalysisForm({
  parcelId,
  onClose,
  onSaved,
}: {
  parcelId: string
  onClose: () => void
  onSaved: () => Promise<void>
}) {
  const [sampledOn, setSampledOn] = useState(todayKey())
  const [rowId, setRowId] = useState('')
  const [treeId, setTreeId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId],
    queryFn: () => listParcelTrees(parcelId),
  })
  const rows = rowsQuery.data ?? []
  const trees = treesQuery.data ?? []
  const rowTrees = rowId ? trees.filter((tree) => tree.row_id === rowId) : []
  const selectedTree = trees.find((tree) => tree.id === treeId)

  const mutation = useMutation({
    mutationFn: () => {
      if (!file || !treeId || !sampledOn) throw new Error('Unesite PDF/fotografiju, datum i sadnicu')
      return uploadParcelSoilAnalysis(parcelId, { file, tree_id: treeId, sampled_on: sampledOn })
    },
    onSuccess: async () => {
      await onSaved()
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : 'Čuvanje nije uspelo')
    },
  })

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!file) {
      setError('Izaberite PDF ili fotografiju analize')
      return
    }
    if (!sampledOn) {
      setError('Unesite datum uzorkovanja')
      return
    }
    if (!treeId) {
      setError('Povežite analizu sa najbližom sadnicom')
      return
    }
    mutation.mutate()
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Nova analiza</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Otpremite PDF ili fotografiju i označite najbližu sadnicu gde je uzet uzorak zemljišta.
            Veliki skenovi se kompresuju automatski (do 400 MB ulaz).
          </p>
        </div>
        <Button type="button" variant="ghost" size="sm" onClick={onClose}>
          Otkaži
        </Button>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>PDF ili fotografija</Label>
              <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2 text-sm">
                <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="truncate">{file ? file.name : 'Izaberite datoteku'}</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf,image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                  className="hidden"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null)
                    event.target.value = ''
                  }}
                />
              </label>
            </div>
            <div className="space-y-1.5">
              <Label>Datum uzorkovanja</Label>
              <Input type="date" value={sampledOn} onChange={(event) => setSampledOn(event.target.value)} />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Red</Label>
              <Select
                value={rowId}
                onChange={(event) => {
                  setRowId(event.target.value)
                  setTreeId('')
                }}
              >
                <option value="">Izaberite red</option>
                {rows.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name ?? rowLabel(row.row_number)}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Najbliža sadnica</Label>
              <div className="flex items-center gap-2">
                <Select
                  className="min-w-0 flex-1"
                  value={treeId}
                  onChange={(event) => {
                    const tree = trees.find((item) => item.id === event.target.value)
                    setTreeId(event.target.value)
                    if (tree?.row_id) setRowId(tree.row_id)
                  }}
                >
                  <option value="">{rowId ? 'Izaberite sadnicu' : 'Prvo izaberite red'}</option>
                  {rowTrees.map((tree) => (
                    <option key={tree.id} value={tree.id}>
                      {tree.public_id}
                    </option>
                  ))}
                </Select>
                <Button type="button" variant="outline" className="shrink-0" onClick={() => setPickerOpen(true)}>
                  <MapPinned className="h-4 w-4" />
                  Mapa
                </Button>
              </div>
              {selectedTree ? (
                <p className="text-[11px] text-muted-foreground">
                  {rowLabel(selectedTree.row_number)} · {selectedTree.public_id}
                </p>
              ) : null}
            </div>
          </div>

          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {mutation.error && !error ? (
            <p className="text-sm text-danger">
              {mutation.error instanceof Error ? mutation.error.message : 'Čuvanje nije uspelo'}
            </p>
          ) : null}

          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Otkaži
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? 'Čuvanje…' : 'Sačuvaj analizu'}
            </Button>
          </div>
        </form>
      </CardContent>

      {pickerOpen ? (
        <OrchardPickerDialog
          parcelId={parcelId}
          mode="tree"
          selectedRowIds={rowId ? [rowId] : []}
          selectedTreeId={treeId || null}
          onToggleRow={() => undefined}
          onSelectTree={(nextTreeId, nextRowId) => {
            setTreeId(nextTreeId)
            setRowId(nextRowId)
            setPickerOpen(false)
          }}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
    </Card>
  )
}
