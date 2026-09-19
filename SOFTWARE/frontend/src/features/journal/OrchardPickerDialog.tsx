import { useQuery } from '@tanstack/react-query'

import { getOrchardTwin } from '@/features/orchard/api'
import { OrchardCanvas } from '@/features/orchard/OrchardCanvas'
import { rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'

type OrchardPickerDialogProps = {
  parcelId: string
  mode: 'rows' | 'tree'
  selectedRowIds: string[]
  selectedTreeId: string | null
  onToggleRow: (rowId: string) => void
  onSelectAllRows?: () => void
  onClearRows?: () => void
  onSelectTree: (treeId: string, rowId: string) => void
  onClose: () => void
}

export function OrchardPickerDialog({
  parcelId,
  mode,
  selectedRowIds,
  selectedTreeId,
  onToggleRow,
  onSelectAllRows,
  onClearRows,
  onSelectTree,
  onClose,
}: OrchardPickerDialogProps) {
  const twinQuery = useQuery({
    queryKey: ['orchard-twin', parcelId],
    queryFn: () => getOrchardTwin(parcelId),
    enabled: Boolean(parcelId),
  })
  const twin = twinQuery.data
  const selectedTree = twin?.trees.find((tree) => tree.id === selectedTreeId)
  const selectedRows = (twin?.rows ?? [])
    .filter((row) => selectedRowIds.includes(row.id))
    .map((row) => rowLabel(row.row_number))

  return (
    <div className="fixed inset-0 z-[2000] flex items-end justify-center bg-foreground/40 p-0 sm:items-center sm:p-4">
      <div className="flex h-[96dvh] w-full flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-xl sm:h-[90vh] sm:rounded-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">
              {mode === 'rows' ? 'Označite redove na zasadu' : 'Označite stablo na zasadu'}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === 'rows'
                ? 'Kliknite red ili stablo da dodate ili uklonite red.'
                : 'Kliknite stablo koje želite da vežete za aktivnost.'}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            Zatvori
          </Button>
        </div>
        <div className="min-h-[40dvh] flex-1 bg-[var(--color-map-soil)] sm:min-h-[28rem]">
          {twinQuery.isLoading ? (
            <p className="p-6 text-sm text-muted-foreground">Učitavanje zasada…</p>
          ) : twin ? (
            <OrchardCanvas
              twin={twin}
              selectedTreeId={selectedTreeId}
              pickMode={mode}
              selectedRowIds={selectedRowIds}
              onToggleRow={onToggleRow}
              onSelectTree={(treeId) => {
                const tree = twin.trees.find((item) => item.id === treeId)
                if (tree) onSelectTree(tree.id, tree.row_id)
              }}
            />
          ) : (
            <p className="p-6 text-sm text-danger">Zasad nije učitan.</p>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5">
          <p className="text-sm text-muted-foreground">
            {mode === 'rows'
              ? selectedRows.length
                ? selectedRows.length > 4
                  ? `Izabrano: ${selectedRows.length} redova`
                  : `Izabrano: ${selectedRows.join(', ')}`
                : 'Nijedan red nije izabran'
              : selectedTree
                ? `Izabrano: ${selectedTree.public_id}`
                : 'Nijedno stablo nije izabrano'}
          </p>
          <div className="flex flex-wrap gap-2">
            {mode === 'rows' ? (
              <>
                <Button type="button" variant="outline" size="sm" onClick={onSelectAllRows}>
                  Svi redovi
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={onClearRows}>
                  Poništi
                </Button>
              </>
            ) : null}
            <Button type="button" size="sm" onClick={onClose}>
              Gotovo
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
