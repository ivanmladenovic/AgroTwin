import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, MapPinned, Plus, X } from 'lucide-react'

import { OrchardPickerDialog } from '@/features/journal/OrchardPickerDialog'
import { listParcelRows, listParcelTrees } from '@/features/orchard/api'
import { rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

export type SoilSampleDraft = {
  key: string
  sampled_on: string
  row_id: string
  tree_id: string
  file: File | null
}

export function emptySoilSample(sampledOn: string): SoilSampleDraft {
  return {
    key: crypto.randomUUID(),
    sampled_on: sampledOn,
    row_id: '',
    tree_id: '',
    file: null,
  }
}

export function soilSamplesError(samples: SoilSampleDraft[]) {
  if (samples.length === 0) return 'Dodajte bar jedan uzorak'
  if (samples.some((sample) => !sample.file || !sample.sampled_on || !sample.tree_id)) {
    return 'Svaki uzorak treba PDF/fotografiju, datum i najbližu sadnicu'
  }
  return null
}

export function SoilAnalysisSamples({
  parcelId,
  samples,
  onChange,
}: {
  parcelId: string
  samples: SoilSampleDraft[]
  onChange: (samples: SoilSampleDraft[]) => void
}) {
  const [pickingKey, setPickingKey] = useState<string | null>(null)
  const rowsQuery = useQuery({
    queryKey: ['parcel-rows', parcelId],
    queryFn: () => listParcelRows(parcelId),
    enabled: Boolean(parcelId),
  })
  const treesQuery = useQuery({
    queryKey: ['parcel-trees', parcelId],
    queryFn: () => listParcelTrees(parcelId),
    enabled: Boolean(parcelId),
  })
  const rows = rowsQuery.data ?? []
  const trees = treesQuery.data ?? []
  const picking = samples.find((sample) => sample.key === pickingKey)

  function update(key: string, patch: Partial<SoilSampleDraft>) {
    onChange(samples.map((sample) => (sample.key === key ? { ...sample, ...patch } : sample)))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <Label>Uzorci analize</Label>
          <p className="mt-1 text-xs text-muted-foreground">
            Za svaki uzorak dodajte PDF ili fotografiju, datum uzorkovanja i najbližu sadnicu.
            Veliki PDF (npr. sken) se automatski kompresuje pri otpremi.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...samples, emptySoilSample(samples[0]?.sampled_on || '')])}>
          <Plus className="h-4 w-4" />
          Dodaj uzorak
        </Button>
      </div>
      {samples.map((sample, index) => {
        const rowTrees = sample.row_id ? trees.filter((tree) => tree.row_id === sample.row_id) : []
        const selectedTree = trees.find((tree) => tree.id === sample.tree_id)
        return (
          <div key={sample.key} className="space-y-3 rounded-xl border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium">Uzorak {index + 1}</p>
              {samples.length > 1 ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  aria-label="Ukloni uzorak"
                  onClick={() => onChange(samples.filter((item) => item.key !== sample.key))}
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">PDF ili fotografija</p>
                <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2 text-sm">
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{sample.file ? sample.file.name : 'Izaberite datoteku'}</span>
                  <input
                    type="file"
                    accept="application/pdf,.pdf,image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                    className="hidden"
                    onChange={(event) => {
                      update(sample.key, { file: event.target.files?.[0] ?? null })
                      event.target.value = ''
                    }}
                  />
                </label>
              </div>
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">Datum uzorkovanja</p>
                <Input type="date" value={sample.sampled_on} onChange={(event) => update(sample.key, { sampled_on: event.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">Red</p>
                <Select
                  value={sample.row_id}
                  onChange={(event) => update(sample.key, { row_id: event.target.value, tree_id: '' })}
                >
                  <option value="">Izaberite red</option>
                  {rows.map((row) => (
                    <option key={row.id} value={row.id}>
                      {rowLabel(row.row_number)}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <p className="text-[11px] font-medium text-muted-foreground">Najbliža sadnica</p>
                <div className="flex items-center gap-2">
                  <Select
                    className="min-w-0 flex-1"
                    value={sample.tree_id}
                    onChange={(event) => {
                      const tree = trees.find((item) => item.id === event.target.value)
                      update(sample.key, { tree_id: event.target.value, row_id: tree?.row_id || sample.row_id })
                    }}
                  >
                    <option value="">{sample.row_id ? 'Izaberite sadnicu' : 'Prvo izaberite red'}</option>
                    {rowTrees.map((tree) => (
                      <option key={tree.id} value={tree.id}>
                        {tree.public_id}
                      </option>
                    ))}
                  </Select>
                  <Button
                    type="button"
                    variant="outline"
                    className="shrink-0"
                    disabled={!parcelId}
                    onClick={() => setPickingKey(sample.key)}
                  >
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
          </div>
        )
      })}
      {picking && parcelId ? (
        <OrchardPickerDialog
          parcelId={parcelId}
          mode="tree"
          selectedRowIds={picking.row_id ? [picking.row_id] : []}
          selectedTreeId={picking.tree_id || null}
          onToggleRow={() => undefined}
          onSelectTree={(treeId, rowId) => {
            update(picking.key, { tree_id: treeId, row_id: rowId })
            setPickingKey(null)
          }}
          onClose={() => setPickingKey(null)}
        />
      ) : null}
    </div>
  )
}
