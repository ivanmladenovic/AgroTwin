import { NavLink } from 'react-router-dom'

import { cn } from '@/shared/lib/utils'

export type SectionTabItem = {
  to: string
  label: string
  end?: boolean
}

export function SectionTabs({ items }: { items: SectionTabItem[] }) {
  return (
    <div className="flex flex-wrap gap-1.5 print:hidden sm:gap-2">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              'rounded-md border px-3 py-1.5 text-sm font-medium transition-colors',
              isActive
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}
