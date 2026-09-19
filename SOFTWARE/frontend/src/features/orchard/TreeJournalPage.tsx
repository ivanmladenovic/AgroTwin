import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'

import { PhotoGallery } from '@/features/health/PhotoGallery'
import { categoryLabel, severityLabel, statusLabel as caseStatusLabel } from '@/features/health/labels'
import { getTreeJournal } from '@/features/orchard/api'
import { healthLabel, statusLabel } from '@/features/orchard/health'
import { formatDate, formatMoney, rowLabel, scopeLabel } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

export function TreeJournalPage() {
  const { parcelId, treeId } = useParams()
  const journalQuery = useQuery({
    queryKey: ['tree-journal', parcelId, treeId],
    queryFn: () => getTreeJournal(parcelId!, treeId!),
    enabled: Boolean(parcelId && treeId),
  })
  const journal = journalQuery.data
  const tree = journal?.tree

  if (journalQuery.isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Učitavanje dnevnika stabla…</div>
  }
  if (!journal || !tree || !parcelId) {
    return <div className="p-6 text-sm text-danger">Stablo nije pronađeno.</div>
  }

  const addActivityTo = `/activities/new?scope=tree&parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}/trees/${tree.id}`
  const reportProblemTo = `/health/new?parcelId=${parcelId}&rowId=${tree.row_id}&treeId=${tree.id}&returnTo=/orchard/${parcelId}/trees/${tree.id}`
  const latestObservations = journal.observations.slice(0, 5)

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kicker">Dnevnik stabla</p>
          <h1 className="mt-1 font-mono text-xl sm:text-2xl">{tree.public_id}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {rowLabel(tree.row_number)} · pozicija {tree.position_in_row}
          </p>
        </div>
        <div className="flex gap-2">
          <Link to={reportProblemTo}>
            <Button size="sm">+ Prijavi problem</Button>
          </Link>
          <Link to={addActivityTo}>
            <Button variant="outline" size="sm">
              + Dodaj aktivnost
            </Button>
          </Link>
          <Link to={`/orchard/${parcelId}`}>
            <Button variant="outline" size="sm">
              Nazad na mapu
            </Button>
          </Link>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-4">
        <Fact label="Sorta" value={tree.variety ?? '—'} />
        <Fact label="Godina sadnje" value={tree.planting_year ? String(tree.planting_year) : '—'} />
        <Fact label="Stanje" value={statusLabel(tree.status)} />
        <Fact label="Zdravlje" value={healthLabel(tree.health_status)} />
      </section>

      <p className="text-sm text-muted-foreground">
        Status zdravlja se izvodi iz otvorenih opažanja. Zapisi ovde nisu potvrđena dijagnoza.
      </p>

      <section className="grid gap-4 md:grid-cols-2">
        <Fact
          label="Direktni trošak stabla"
          value={formatMoney(journal.direct_cost_total, journal.currency)}
          hint="Troškovi evidentirani samo na ovom stablu"
        />
        <Fact
          label="Povezani troškovi voćnjaka"
          value={formatMoney(journal.orchard_cost_total, journal.currency)}
          hint="Aktivnosti reda i parcele još nisu raspoređene na ovo stablo"
        />
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Otvoreni slučajevi</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {journal.open_cases.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nema otvorenih opažanja za ovo stablo.</p>
          ) : (
            journal.open_cases.map((item) => (
              <Link key={item.id} to={`/health/${item.id}`} className="block text-sm hover:underline">
                <p className="font-medium">{item.title}</p>
                <p className="text-muted-foreground">
                  {formatDate(item.detected_on)} · {categoryLabel(item.category)} · {severityLabel(item.severity)} ·{' '}
                  {caseStatusLabel(item.status)}
                </p>
              </Link>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hronologija</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {journal.timeline.length === 0 ? (
            <p className="text-sm text-muted-foreground">Još nema događaja za ovo stablo.</p>
          ) : (
            journal.timeline.map((event) => {
              const href =
                event.disease_id && (event.kind === 'disease' || event.kind === 'observation')
                  ? `/health/${event.disease_id}`
                  : event.activity_id
                    ? `/activities/${event.activity_id}`
                    : null
              const inner = (
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-xs text-muted-foreground">{formatDate(event.occurred_on)}</p>
                    <p className="mt-1 font-medium">{event.title}</p>
                    {event.subtitle ? <p className="text-sm text-muted-foreground">{event.subtitle}</p> : null}
                  </div>
                  <p className="font-mono text-sm">
                    {event.amount != null ? formatMoney(event.amount, event.currency ?? journal.currency) : '—'}
                  </p>
                </div>
              )
              return href ? (
                <Link
                  key={`${event.kind}-${event.activity_id ?? event.observation_id ?? event.disease_id}-${event.occurred_on}`}
                  to={href}
                  className="block hover:bg-muted/40"
                >
                  {inner}
                </Link>
              ) : (
                <div key={`${event.kind}-${event.activity_id ?? event.disease_id}-${event.occurred_on}`}>{inner}</div>
              )
            })
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Najnovija opažanja</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {latestObservations.length === 0 ? (
              <p className="text-sm text-muted-foreground">Još nema zabeleženih opažanja.</p>
            ) : (
              latestObservations.map((observation) => (
                <Link
                  key={observation.id}
                  to={`/health/${observation.disease_case_id}`}
                  className="block text-sm hover:underline"
                >
                  <p className="font-mono text-xs text-muted-foreground">{formatDate(observation.observed_on)}</p>
                  <p className="mt-1">{observation.symptoms || observation.notes || 'Opažanje'}</p>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Najnovije fotografije</CardTitle>
          </CardHeader>
          <CardContent>
            <PhotoGallery photos={journal.photos.slice(0, 6)} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Aktivnosti</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {journal.activities.length === 0 ? (
              <p className="text-sm text-muted-foreground">Još nema aktivnosti na nivou stabla.</p>
            ) : (
              journal.activities.map((activity) => (
                <Link
                  key={activity.id}
                  to={`/activities/${activity.id}`}
                  className="flex items-center justify-between text-sm hover:underline"
                >
                  <span>
                    {formatDate(activity.performed_on)} · {activity.activity_type.name}
                  </span>
                  <span className="font-mono">{formatMoney(activity.total_cost, activity.currency)}</span>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Svi zabeleženi slučajevi</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {journal.diseases.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nema zabeleženih slučajeva.</p>
            ) : (
              journal.diseases.map((item) => (
                <Link key={item.id} to={`/health/${item.id}`} className="block text-sm hover:underline">
                  <p className="font-medium">{item.title}</p>
                  <p className="text-muted-foreground">
                    {formatDate(item.detected_on)} · {severityLabel(item.severity)} · {caseStatusLabel(item.status)}
                  </p>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Troškovi</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {journal.costs.length === 0 ? (
              <p className="text-sm text-muted-foreground">Još nema direktnih troškova stabla.</p>
            ) : (
              journal.costs.map((cost) => (
                <div key={cost.id} className="flex items-center justify-between text-sm">
                  <span>
                    {cost.description} · {cost.cost_category.name}
                  </span>
                  <span className="font-mono">{formatMoney(cost.amount, cost.currency)}</span>
                </div>
              ))
            )}
            {journal.related_costs.length > 0 ? (
              <p className="pt-2 text-xs text-muted-foreground">
                Povezani troškovi voćnjaka ({scopeLabel('parcel')} / red) ukupno{' '}
                {formatMoney(journal.orchard_cost_total, journal.currency)} i nisu raspoređeni na ovo stablo.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Fact({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-lg font-medium">{value}</p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}
