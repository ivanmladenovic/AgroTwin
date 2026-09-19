export function dateKey(year: number, month: number, day: number) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function todayKey() {
  const now = new Date()
  return dateKey(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

export function monthName(year: number, month: number) {
  const label = new Intl.DateTimeFormat('sr-Latn-RS', { month: 'long' }).format(new Date(year, month - 1, 1))
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function shiftMonth(year: number, month: number, delta: number) {
  const date = new Date(year, month - 1 + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

export function monthWindow(centerYear: number, centerMonth: number, before: number, after: number) {
  return Array.from({ length: before + after + 1 }, (_, index) => shiftMonth(centerYear, centerMonth, index - before))
}

export function daysInMonth(year: number, month: number) {
  return new Date(year, month, 0).getDate()
}

export function monthBounds(year: number, month: number) {
  return {
    from: dateKey(year, month, 1),
    to: dateKey(year, month, daysInMonth(year, month)),
  }
}

export const WEEKDAYS = ['P', 'U', 'S', 'Č', 'P', 'S', 'N']

export type CalendarCell = {
  key: string
  day: number
  inMonth: boolean
}

export function monthCells(year: number, month: number): CalendarCell[] {
  const first = new Date(year, month - 1, 1)
  const startWeekday = (first.getDay() + 6) % 7
  const daysInMonthCount = daysInMonth(year, month)
  const cells: CalendarCell[] = []
  for (let i = 0; i < startWeekday; i += 1) {
    cells.push({ key: `pad-${month}-${i}`, day: 0, inMonth: false })
  }
  for (let day = 1; day <= daysInMonthCount; day += 1) {
    cells.push({ key: dateKey(year, month, day), day, inMonth: true })
  }
  while (cells.length % 7 !== 0) {
    cells.push({ key: `end-${month}-${cells.length}`, day: 0, inMonth: false })
  }
  return cells
}
