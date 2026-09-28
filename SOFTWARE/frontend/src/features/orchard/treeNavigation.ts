import type { TreeMapItem } from '@/shared/api/types'

export type TreeNavDirection = 'up' | 'down' | 'left' | 'right'

export function plantedTrees(trees: TreeMapItem[]) {
  return trees.filter((tree) => tree.status !== 'removed')
}

/** Left/right = same row; up/down = neighboring row, closest position. */
export function neighborTreeId(
  trees: TreeMapItem[],
  currentId: string,
  direction: TreeNavDirection,
): string | null {
  const current = trees.find((tree) => tree.id === currentId && tree.status !== 'removed')
  if (!current) return null

  const active = plantedTrees(trees)

  if (direction === 'left' || direction === 'right') {
    const row = active
      .filter((tree) => tree.row_number === current.row_number)
      .sort((a, b) => a.position_in_row - b.position_in_row)
    const index = row.findIndex((tree) => tree.id === currentId)
    if (index < 0) return null
    const next = direction === 'left' ? row[index - 1] : row[index + 1]
    return next?.id ?? null
  }

  const targetRow = direction === 'up' ? current.row_number - 1 : current.row_number + 1
  const candidates = active.filter((tree) => tree.row_number === targetRow)
  if (candidates.length === 0) return null

  candidates.sort(
    (a, b) =>
      Math.abs(a.position_in_row - current.position_in_row) -
      Math.abs(b.position_in_row - current.position_in_row),
  )
  return candidates[0]?.id ?? null
}

export function canNavigate(
  trees: TreeMapItem[],
  currentId: string,
): Record<TreeNavDirection, boolean> {
  return {
    up: Boolean(neighborTreeId(trees, currentId, 'up')),
    down: Boolean(neighborTreeId(trees, currentId, 'down')),
    left: Boolean(neighborTreeId(trees, currentId, 'left')),
    right: Boolean(neighborTreeId(trees, currentId, 'right')),
  }
}
