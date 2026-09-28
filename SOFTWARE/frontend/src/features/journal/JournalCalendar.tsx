import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { activityCalendarKind, activityStatusLabel, type CalendarKind } from '@/features/journal/labels'
import {
  journalCalendarSpan,
  monthBounds,
  monthCells,
  monthName,
  monthRange,
  shiftMonth,
  todayKey,
  WEEKDAYS,
} from '@/features/journal/calendar'
import type { Activity } from '@/shared/api/types'
import { activityTarget, formatDate, formatMoney, formatWorkQuantities, scopeLabel } from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/ui/button'
import { Select } from '@/shared/ui/select'

const KIND_DOT: Record<CalendarKind, string> = {
  done: 'bg-ok',
  planned: 'bg-accent',
  overdue: 'bg-danger',
}

type MonthCursor = { year: number; month: number }

type JournalCalendarProps = {
  selectedDay: string | null
  activities: Activity[]
  onSelectDay: (day: string) => void
  returnTo?: string
}

export function JournalCalendar({
  selectedDay,
  activities,
  onSelectDay,
  returnTo = '/journal',
}: JournalCalendarProps) {
  const today = todayKey()
  const now = useMemo(() => {
    const date = new Date()
    return { year: date.getFullYear(), month: date.getMonth() + 1 }
  }, [])
  const span = useMemo(() => journalCalendarSpan(new Date(now.year, now.month - 1, 1)), [now.month, now.year])
  const months = useMemo(
    () => monthRange(span.fromYear, span.fromMonth, span.toYear, span.toMonth),
    [span.fromMonth, span.fromYear, span.toMonth, span.toYear],
  )
  const years = useMemo(() => {
    const list: number[] = []
    for (let year = span.fromYear; year <= span.toYear; year += 1) list.push(year)
    return list
  }, [span.fromYear, span.toYear])
  const scrollerRef = useRef<HTMLDivElement>(null)
  const monthRefs = useRef(new Map<string, HTMLElement>())
  const pendingScroll = useRef<MonthCursor | null>(null)
  const navigationReady = useRef(false)
  const [visible, setVisible] = useState<MonthCursor>(now)
  const visibleRef = useRef(visible)
  visibleRef.current = visible

  const canGoPrev = !(visible.year === span.fromYear && visible.month === span.fromMonth)
  const canGoNext = !(visible.year === span.toYear && visible.month === span.toMonth)

  const byDay = new Map<string, Activity[]>()
  for (const activity of activities) {
    byDay.set(activity.performed_on, [...(byDay.get(activity.performed_on) ?? []), activity])
  }
  const selected = selectedDay ? (byDay.get(selectedDay) ?? []) : []
  const visibleBounds = monthBounds(visible.year, visible.month)
  const visibleCounts = { done: 0, planned: 0, overdue: 0 }
  for (const activity of activities) {
    if (activity.performed_on < visibleBounds.from || activity.performed_on > visibleBounds.to) continue
    const kind = activityCalendarKind(activity.status, activity.performed_on, today)
    if (kind) visibleCounts[kind] += 1
  }

  function monthKey(item: MonthCursor) {
    return `${item.year}-${String(item.month).padStart(2, '0')}`
  }

  function scrollToMonth(item: MonthCursor, behavior: ScrollBehavior = 'smooth') {
    const clamped = clampMonth(item, span)
    const root = scrollerRef.current
    const node = monthRefs.current.get(monthKey(clamped))
    if (!root || !node) {
      pendingScroll.current = clamped
      setVisible(clamped)
      return
    }
    pendingScroll.current = null
    root.scrollTo({ top: node.offsetTop, behavior })
    setVisible(clamped)
  }

  useEffect(() => {
    navigationReady.current = false
    pendingScroll.current = now
    const timer = window.setTimeout(() => {
      scrollToMonth(now, 'auto')
      navigationReady.current = true
    }, 50)
    return () => window.clearTimeout(timer)
    // Intentionally only when "today" changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [now])

  useEffect(() => {
    const target = pendingScroll.current
    if (!target) return
    const frame = window.requestAnimationFrame(() => scrollToMonth(target, 'auto'))
    return () => window.cancelAnimationFrame(frame)
  }, [months])

  useEffect(() => {
    const root = scrollerRef.current
    if (!root) return
    let locked = false
    let unlockTimer = 0
    function onWheel(event: WheelEvent) {
      if (Math.abs(event.deltaY) < 12) return
      event.preventDefault()
      if (locked) return
      locked = true
      const current = visibleRef.current
      scrollToMonth(shiftMonth(current.year, current.month, event.deltaY > 0 ? 1 : -1))
      unlockTimer = window.setTimeout(() => {
        locked = false
      }, 420)
    }
    root.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      root.removeEventListener('wheel', onWheel)
      window.clearTimeout(unlockTimer)
    }
  }, [months, span])

  useEffect(() => {
    const root = scrollerRef.current
    if (!root) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (!navigationReady.current) return
        const best = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        const key = best?.target.getAttribute('data-month')
        if (!key) return
        const [year, month] = key.split('-').map(Number)
        setVisible((current) => (current.year === year && current.month === month ? current : { year, month }))
      },
      { root, threshold: 0.55 },
    )
    for (const node of monthRefs.current.values()) observer.observe(node)
    return () => observer.disconnect()
  }, [months])

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-stretch">
      <div className="flex min-w-0 flex-col gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => scrollToMonth(shiftMonth(visible.year, visible.month, -1))}
              disabled={!canGoPrev}
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
              aria-label="Prethodni mesec"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <Select
              aria-label="Mesec"
              className="h-11 w-[9.5rem] bg-background lg:h-11"
              value={String(visible.month)}
              onChange={(event) => scrollToMonth({ year: visible.year, month: Number(event.target.value) })}
            >
              {Array.from({ length: 12 }, (_, index) => {
                const month = index + 1
                return (
                  <option key={month} value={month}>
                    {monthName(visible.year, month)}
                  </option>
                )
              })}
            </Select>
            <Select
              aria-label="Godina"
              className="h-11 w-[5.5rem] bg-background lg:h-11"
              value={String(visible.year)}
              onChange={(event) => scrollToMonth({ year: Number(event.target.value), month: visible.month })}
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={() => scrollToMonth(shiftMonth(visible.year, visible.month, 1))}
              disabled={!canGoNext}
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
              aria-label="Sledeći mesec"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            {visible.year !== now.year || visible.month !== now.month ? (
              <button
                type="button"
                onClick={() => scrollToMonth(now)}
                className="h-11 rounded-lg border border-border px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                Danas
              </button>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <Legend color={KIND_DOT.done} label={`Urađeno ${visibleCounts.done}`} />
            <Legend color={KIND_DOT.planned} label={`Planirano ${visibleCounts.planned}`} />
            <Legend color={KIND_DOT.overdue} label={`Kasni ${visibleCounts.overdue}`} />
          </div>
        </div>

        <div
          ref={scrollerRef}
          className="relative h-[28rem] overflow-y-auto overscroll-y-contain rounded-xl border border-border bg-card snap-y snap-mandatory"
        >
          {months.map((item) => (
            <div
              key={monthKey(item)}
              ref={(node) => {
                if (node) monthRefs.current.set(monthKey(item), node)
                else monthRefs.current.delete(monthKey(item))
              }}
              data-month={monthKey(item)}
              className="flex h-[28rem] shrink-0 snap-start snap-always flex-col px-5 py-4"
            >
              <MonthGrid
                year={item.year}
                month={item.month}
                today={today}
                selectedDay={selectedDay}
                byDay={byDay}
                onSelectDay={onSelectDay}
              />
            </div>
          ))}
        </div>
      </div>

      <section className="flex min-h-0 flex-col rounded-xl border border-border bg-card p-5">
        {selectedDay ? (
          <>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="kicker">Dan</p>
                <h2 className="mt-1 text-lg font-semibold">{formatDate(selectedDay)}</h2>
              </div>
              <Link to={createPath(selectedDay, today, returnTo)}>
                <Button size="sm">{selectedDay > today ? 'Planiraj za ovaj dan' : 'Dodaj za ovaj dan'}</Button>
              </Link>
            </div>
            {selected.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Ništa nije zabeleženo. Unesite urađeni rad ili planirajte šta treba uraditi.
              </p>
            ) : (
              <div className="min-h-0 space-y-2 overflow-y-auto">
                {selected.map((activity) => (
                  <ActivityRow key={activity.id} activity={activity} today={today} returnTo={returnTo} />
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Izaberite dan u kalendaru.</p>
        )}
      </section>
    </div>
  )
}

function MonthGrid({
  year,
  month,
  today,
  selectedDay,
  byDay,
  onSelectDay,
}: {
  year: number
  month: number
  today: string
  selectedDay: string | null
  byDay: Map<string, Activity[]>
  onSelectDay: (day: string) => void
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="grid grid-cols-7 text-center">
        {WEEKDAYS.map((label, index) => (
          <span key={`${label}-${index}`} className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {label}
          </span>
        ))}
      </div>
      <div className="grid flex-1 grid-cols-7 gap-1 text-center">
        {monthCells(year, month).map((cell) => {
          if (!cell.inMonth) {
            return <span key={cell.key} />
          }
          const items = byDay.get(cell.key) ?? []
          const kinds = uniqueKinds(items, today)
          const isToday = cell.key === today
          const isSelected = cell.key === selectedDay
          return (
            <button
              key={cell.key}
              type="button"
              onClick={() => onSelectDay(cell.key)}
              className={cn(
                'flex min-h-11 flex-col items-center justify-center rounded-lg px-1 py-1 text-sm tabular-nums transition-colors',
                isSelected ? 'bg-primary text-primary-foreground' : 'hover:bg-muted',
                isToday && !isSelected ? 'ring-1 ring-accent' : '',
              )}
            >
              <span>{cell.day}</span>
              {kinds.length > 0 ? (
                <span className="mt-1 flex h-1.5 items-center gap-0.5">
                  {kinds.map((kind) => (
                    <span
                      key={kind}
                      className={cn('h-1.5 w-1.5 rounded-full', isSelected ? 'bg-primary-foreground' : KIND_DOT[kind])}
                    />
                  ))}
                </span>
              ) : (
                <span className="mt-1 h-1.5" />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function uniqueKinds(items: Activity[], today: string): CalendarKind[] {
  const seen = new Set<CalendarKind>()
  for (const item of items) {
    const kind = activityCalendarKind(item.status, item.performed_on, today)
    if (kind) seen.add(kind)
  }
  return (['overdue', 'planned', 'done'] as CalendarKind[]).filter((kind) => seen.has(kind))
}

function ActivityRow({
  activity,
  today,
  returnTo,
}: {
  activity: Activity
  today: string
  returnTo: string
}) {
  const kind = activityCalendarKind(activity.status, activity.performed_on, today)
  return (
    <Link to={`/activities/${activity.id}?returnTo=${encodeURIComponent(returnTo)}`} className="block">
      <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5 hover:bg-muted/70">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{activity.title}</p>
          <p className="text-xs text-muted-foreground">
            {scopeLabel(activity.scope_type)} · {activityTarget(activity)}
            {formatWorkQuantities(activity.line_items) ? ` · ${formatWorkQuantities(activity.line_items)}` : ''}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide',
              kind === 'done'
                ? 'bg-ok/10 text-ok'
                : kind === 'overdue'
                  ? 'bg-danger/10 text-danger'
                  : 'bg-accent/10 text-accent',
            )}
          >
            {kind === 'overdue' ? 'Kasni' : activityStatusLabel(activity.status)}
          </span>
          <span className="font-mono text-xs">{formatMoney(activity.total_cost, activity.currency)}</span>
        </div>
      </div>
    </Link>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn('h-2 w-2 rounded-full', color)} />
      {label}
    </span>
  )
}

function createPath(day: string, today: string, returnTo: string) {
  const status = day > today ? 'planned' : 'completed'
  const params = new URLSearchParams({ date: day, status, returnTo })
  return `/activities/new?${params.toString()}`
}

function clampMonth(item: MonthCursor, span: { fromYear: number; fromMonth: number; toYear: number; toMonth: number }) {
  const value = item.year * 12 + item.month
  const from = span.fromYear * 12 + span.fromMonth
  const to = span.toYear * 12 + span.toMonth
  if (value < from) return { year: span.fromYear, month: span.fromMonth }
  if (value > to) return { year: span.toYear, month: span.toMonth }
  return item
}
