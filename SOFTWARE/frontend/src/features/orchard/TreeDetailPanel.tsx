import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'

import { listDiseaseCases, resolveDiseaseCase } from '@/features/health/cases'
import { categoryLabel, severityLabel } from '@/features/health/labels'
import { getTreeJournal } from '@/features/orchard/api'
import { healthLabel, statusLabel } from '@/features/orchard/health'
import type { DiseaseCase, TreeDetail } from '@/shared/api/types'
import { formatDate, formatMoney, rowLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'

import { tr } from '@/shared/i18n/i18n'
export function TreeDetailPanel({
  tree,
  parcelId,
  onClose,
}: {
  tree: TreeDetail
  parcelId: string
  onClose: () => void
}) {
  const panelRef = useRef<HTMLElement | null>(null)
  const queryClient = useQueryClient()
  const mapReturn = encodeURIComponent(`/orchard/${parcelId}?tree=${tree.id}`)
  const openCasesKey = ['disease-cases', 'tree', tree.id, 'open'] as const

  useEffect(() => {
    const panel = panelRef.current
    if (!panel) return
    const main = document.querySelector<HTMLElement>('[data-app-scroll="main"]')

    function scrollToPanel() {
      if (!main) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' })
        return
      }
      const mainRect = main.getBoundingClientRect()
      const panelRect = panel.getBoundingClientRect()
      const nextTop = main.scrollTop + (panelRect.top - mainRect.top) - 16
      main.scrollTo({ top: Math.max(0, nextTop), behavior: 'smooth' })
    }

    // Wait for layout after tree detail mounts (map stays put; panel is below).
    const timers = [0, 120, 280].map((ms) => window.setTimeout(scrollToPanel, ms))
    return () => timers.forEach((id) => window.clearTimeout(id))
  }, [tree.id])

  const journalQuery = useQuery({
    queryKey: ['tree-journal', parcelId, tree.id],
    queryFn: () => getTreeJournal(parcelId, tree.id),
  })

  const openCasesQuery = useQuery({
    queryKey: openCasesKey,
    queryFn: async () => {
      const cases = await listDiseaseCases({ tree_id: tree.id })
      return cases.filter((item) => item.status !== 'resolved')
    },
  })
  const openCases = openCasesQuery.data ?? []
  const showProblems = tree.disease_issue_count > 0 || openCases.length > 0

  const resolveMutation = useMutation({
    mutationFn: async (caseId: string) => {
      try {
        return await resolveDiseaseCase(caseId)
      } catch (error) {
        if (error instanceof Error && 'status' in error && (error as { status: number }).status === 404) {
          return null
        }
        throw error
      }
    },
    onMutate: async (caseId) => {
      await queryClient.cancelQueries({ queryKey: openCasesKey })
      const previous = queryClient.getQueryData<DiseaseCase[]>(openCasesKey)
      queryClient.setQueryData<DiseaseCase[]>(openCasesKey, (current) =>
        (current ?? []).filter((item) => item.id !== caseId),
      )
      return { previous }
    },
    onError: (_error, _caseId, context) => {
      if (context?.previous) queryClient.setQueryData(openCasesKey, context.previous)
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ['disease-cases'] })
      await queryClient.invalidateQueries({ queryKey: ['orchard-twin'] })
      await queryClient.invalidateQueries({ queryKey: ['tree-detail'] })
      await queryClient.invalidateQueries({ queryKey: ['tree-journal'] })
    },
  })

  const journal = journalQuery.data
  const timeline = (journal?.timeline ?? []).slice(0, 8)
  const facts = [
    { label: tr('Red'), value: rowLabel(tree.row_number) },
    { label: tr('Pozicija'), value: String(tree.position_in_row) },
    { label: tr('Sorta'), value: tree.variety ?? '—' },
    { label: tr('Sadnja'), value: tree.planting_year ? String(tree.planting_year) : '—' },
    { label: tr('Stanje'), value: statusLabel(tree.status) },
    { label: tr('Zdravlje'), value: healthLabel(tree.health_status) },
    { label: tr('Aktivnosti'), value: String(tree.activity_count) },
    { label: tr('Problemi'), value: String(Math.max(tree.disease_issue_count, openCases.length)) },
    { label: tr('Trošak'), value: formatMoney(tree.total_cost) },
  ]

  return (
    <section
      ref={panelRef}
      className="scroll-mt-4 overflow-hidden rounded-2xl border border-border bg-card shadow-sm"
      aria-label={tr('Detalji stabla {{id}}', { id: tree.public_id })}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <p className="kicker">{tr("Stablo")}</p>
          <h2 className="mt-0.5 font-mono text-lg font-semibold tracking-tight sm:text-xl">
            {tree.public_id}
            {tree.variety ? (
              <span className="ml-2 font-sans text-sm font-normal text-muted-foreground">
                · {tree.variety}
              </span>
            ) : null}
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {tr('Informacije i istorija · status zdravlja nije potvrđena dijagnoza')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to={`/health/new?parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=${mapReturn}`}
          >
            <Button size="sm">{tr('+ Prijavi problem')}</Button>
          </Link>
          <Link
            to={`/activities/new?scope=tree&parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=${mapReturn}`}
          >
            <Button size="sm" variant="outline">
              {tr('+ Dodaj aktivnost')}
            </Button>
          </Link>
          <Link to={`/orchard/${parcelId}/trees/${tree.id}`}>
            <Button size="sm" variant="outline">
              {tr('Pun dnevnik')}
            </Button>
          </Link>
          <Button type="button" size="sm" variant="ghost" onClick={onClose} aria-label={tr('Zatvori')}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
        <div className="space-y-4 border-b border-border p-4 lg:border-b-0 lg:border-r">
          <dl className="grid grid-cols-2 gap-x-3 gap-y-2.5 sm:grid-cols-3 lg:grid-cols-2">
            {facts.map((field) => (
              <div key={field.label} className="min-w-0">
                <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  {field.label}
                </dt>
                <dd className="mt-0.5 truncate text-sm font-medium" title={field.value}>
                  {field.value}
                </dd>
              </div>
            ))}
          </dl>

          {showProblems ? (
            <div className="space-y-2 rounded-xl border border-border p-3">
              <p className="text-xs font-semibold">{tr('Otvoreni problemi')}</p>
              {openCasesQuery.isLoading ? (
                <p className="text-xs text-muted-foreground">{tr('Učitavanje…')}</p>
              ) : openCases.length === 0 ? (
                <p className="text-xs text-muted-foreground">{tr('Nema otvorenih problema.')}</p>
              ) : (
                openCases.map((item) => (
                  <div
                    key={item.id}
                    className="space-y-1.5 border-t border-border/70 pt-2 first:border-0 first:pt-0"
                  >
                    <Link
                      to={`/health/${item.id}?returnTo=${mapReturn}`}
                      className="block text-sm font-medium hover:underline"
                    >
                      {item.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(item.detected_on)} · {categoryLabel(item.category)} ·{' '}
                      {severityLabel(item.severity)}
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      className="h-8 w-full text-xs"
                      disabled={resolveMutation.isPending}
                      onClick={() => resolveMutation.mutate(item.id)}
                    >
                      {resolveMutation.isPending && resolveMutation.variables === item.id
                        ? tr('Uklanjanje…')
                        : tr('Ukloni problem')}
                    </Button>
                  </div>
                ))
              )}
            </div>
          ) : null}
        </div>

        <div className="p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{tr('Istorija')}</h3>
            <Link
              to={`/orchard/${parcelId}/trees/${tree.id}`}
              className="text-xs font-medium text-primary hover:underline"
            >
              {tr('Vidi sve')}
            </Link>
          </div>
          {journalQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">{tr('Učitavanje istorije…')}</p>
          ) : journalQuery.isError ? (
            <p className="text-sm text-danger">{tr('Istorija nije učitana.')}</p>
          ) : timeline.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {tr('Još nema događaja za ovo stablo. Dodajte aktivnost ili prijavi problem.')}
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {timeline.map((event) => {
                const href =
                  event.disease_id && (event.kind === 'disease' || event.kind === 'observation')
                    ? `/health/${event.disease_id}?returnTo=${mapReturn}`
                    : event.activity_id
                      ? `/activities/${event.activity_id}?returnTo=${mapReturn}`
                      : null
                const content = (
                  <div className="flex items-start justify-between gap-3 px-3 py-2.5">
                    <div className="min-w-0">
                      <p className="font-mono text-[11px] text-muted-foreground">
                        {formatDate(event.occurred_on)}
                        <span className="mx-1.5">·</span>
                        {event.kind === 'activity'
                          ? tr('aktivnost')
                          : event.kind === 'observation'
                            ? tr('opažanje')
                            : tr('problem')}
                      </p>
                      <p className="mt-0.5 text-sm font-medium">{event.title}</p>
                      {event.subtitle ? (
                        <p className="text-xs text-muted-foreground">{event.subtitle}</p>
                      ) : null}
                    </div>
                    {event.amount != null ? (
                      <p className="shrink-0 font-mono text-xs tabular-nums">
                        {formatMoney(event.amount, event.currency ?? journal?.currency)}
                      </p>
                    ) : null}
                  </div>
                )
                return (
                  <li key={`${event.kind}-${event.activity_id ?? event.observation_id ?? event.disease_id}-${event.occurred_on}-${event.title}`}>
                    {href ? (
                      <Link to={href} className="block hover:bg-muted/40">
                        {content}
                      </Link>
                    ) : (
                      content
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
