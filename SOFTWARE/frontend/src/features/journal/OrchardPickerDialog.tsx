import { useQuery } from '@tanstack/react-query'

import { getOrchardTwin } from '@/features/orchard/api'
import { OrchardCanvas } from '@/features/orchard/OrchardCanvas'
import { rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { tr } from '@/shared/i18n/i18n'

type OrchardPickerDialogProps = {
  parcelId: string
  mode: 'rows' | 'tree' | 'trees'
  selectedRowIds: string[]
  selectedTreeId: string | null
  selectedTreeIds?: string[]
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
  selectedTreeIds = [],
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
  const selectedTrees = (twin?.trees ?? []).filter((tree) => selectedTreeIds.includes(tree.id))
  const selectedRows = (twin?.rows ?? [])
    .filter((row) => selectedRowIds.includes(row.id))
    .map((row) => rowLabel(row.row_number))

  return (
    <div className="fixed inset-0 z-[2000] flex items-end justify-center bg-foreground/40 p-0 sm:items-center sm:p-4">
      <div className="flex h-[96dvh] w-full flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-xl sm:h-[90vh] sm:rounded-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">
              {mode === 'rows' ? tr('Označite redove na zasadu') : mode === 'trees' ? tr('Označite sadnice na zasadu') : tr('Označite stablo na zasadu')}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {mode === 'rows'
                ? tr('Kliknite red ili stablo da dodate ili uklonite red.')
                : mode === 'trees'
                  ? tr('Kliknite sadnice koje želite da prijavite. Ponovni klik skida oznaku.')
                  : tr('Kliknite stablo koje želite da vežete.')}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={onClose}>
            {tr('Zatvori')}
          </Button>
        </div>
        <div className="min-h-[40dvh] flex-1 bg-[var(--color-map-soil)] sm:min-h-[28rem]">
          {twinQuery.isLoading ? (
            <p className="p-6 text-sm text-muted-foreground">{tr('Učitavanje zasada…')}</p>
          ) : twin ? (
            <OrchardCanvas
              twin={twin}
              selectedTreeId={selectedTreeId}
              pickMode={mode === 'rows' ? 'rows' : mode === 'trees' ? 'trees' : 'tree'}
              selectedRowIds={selectedRowIds}
              selectedTreeIds={selectedTreeIds}
              onToggleRow={onToggleRow}
              onSelectTree={(treeId) => {
                const tree = twin.trees.find((item) => item.id === treeId)
                if (tree) onSelectTree(tree.id, tree.row_id)
              }}
            />
          ) : (
            <p className="p-6 text-sm text-danger">{tr('Zasad nije učitan.')}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5">
          <p className="text-sm text-muted-foreground">
            {mode === 'rows'
                ? selectedRows.length
                  ? selectedRows.length > 4
                    ? tr('Izabrano: {{count}} redova', { count: selectedRows.length })
                    : tr('Izabrano: {{rows}}', { rows: selectedRows.join(', ') })
                : tr('Nijedan red nije izabran')
              : mode === 'trees'
                ? selectedTrees.length
                  ? tr('Izabrano: {{count}} sadnica', { count: selectedTrees.length })
                  : tr('Nijedna sadnica nije izabrana')
                : selectedTree
                  ? tr('Izabrano: {{id}}', { id: selectedTree.public_id })
                  : tr('Nijedno stablo nije izabrano')}
          </p>
          <div className="flex flex-wrap gap-2">
            {mode === 'rows' ? (
              <>
                <Button type="button" variant="outline" size="sm" onClick={onSelectAllRows}>
                  {tr('Svi redovi')}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={onClearRows}>
                  {tr('Poništi')}
                </Button>
              </>
            ) : null}
            <Button type="button" size="sm" onClick={onClose}>
              {tr('Gotovo')}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
