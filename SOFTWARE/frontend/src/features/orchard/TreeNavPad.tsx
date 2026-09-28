import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from 'lucide-react'

import type { TreeNavDirection } from '@/features/orchard/treeNavigation'
import { cn } from '@/shared/lib/utils'

export function TreeNavPad({
  enabled,
  onNavigate,
}: {
  enabled: Record<TreeNavDirection, boolean>
  onNavigate: (direction: TreeNavDirection) => void
}) {
  return (
    <div
      className="grid w-[7.25rem] grid-cols-3 grid-rows-3 gap-1 rounded-xl border border-border/80 bg-card/95 p-1.5 shadow-md backdrop-blur-sm"
      role="group"
      aria-label="Kretanje kroz sadnice"
    >
      <span />
      <NavButton
        label="Prethodni red"
        direction="up"
        enabled={enabled.up}
        onNavigate={onNavigate}
        icon={ChevronUp}
      />
      <span />
      <NavButton
        label="Prethodna sadnica"
        direction="left"
        enabled={enabled.left}
        onNavigate={onNavigate}
        icon={ChevronLeft}
      />
      <span className="flex items-center justify-center">
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />
      </span>
      <NavButton
        label="Sledeća sadnica"
        direction="right"
        enabled={enabled.right}
        onNavigate={onNavigate}
        icon={ChevronRight}
      />
      <span />
      <NavButton
        label="Sledeći red"
        direction="down"
        enabled={enabled.down}
        onNavigate={onNavigate}
        icon={ChevronDown}
      />
      <span />
    </div>
  )
}

function NavButton({
  label,
  direction,
  enabled,
  onNavigate,
  icon: Icon,
}: {
  label: string
  direction: TreeNavDirection
  enabled: boolean
  onNavigate: (direction: TreeNavDirection) => void
  icon: typeof ChevronUp
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={!enabled}
      onClick={(event) => {
        event.stopPropagation()
        onNavigate(direction)
      }}
      className={cn(
        'inline-flex h-10 w-full items-center justify-center rounded-lg border border-border bg-background text-foreground touch-manipulation',
        enabled ? 'active:bg-muted' : 'opacity-35',
      )}
    >
      <Icon className="h-5 w-5" />
    </button>
  )
}
