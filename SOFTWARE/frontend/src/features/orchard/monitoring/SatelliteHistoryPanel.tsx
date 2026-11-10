import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { getParcelSatelliteHistory } from '@/features/orchard/api'
import { anomalyKindLabel, zoneKeyLabel } from '@/features/orchard/monitoring/satelliteLabels'
import type { SatelliteHistoryPoint } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

import { tr } from '@/shared/i18n/i18n'
type IndexId = 'ndvi' | 'ndre' | 'ndwi'

const INDEXES: { id: IndexId; label: string; color: string }[] = [
  { id: 'ndvi', label: 'NDVI', color: '#3f7d4e' },
  { id: 'ndre', label: 'NDRE', color: '#1d6f8a' },
  { id: 'ndwi', label: 'NDWI', color: '#b86e1a' },
]

function meanKey(index: IndexId): 'ndvi_mean' | 'ndre_mean' | 'ndwi_mean' {
  if (index === 'ndre') return 'ndre_mean'
  if (index === 'ndwi') return 'ndwi_mean'
  return 'ndvi_mean'
}

function deltaKey(index: IndexId): 'ndvi_delta' | 'ndre_delta' | 'ndwi_delta' {
  if (index === 'ndre') return 'ndre_delta'
  if (index === 'ndwi') return 'ndwi_delta'
  return 'ndvi_delta'
}

function reliableKey(
  index: IndexId,
): 'ndvi_comparison_reliable' | 'ndre_comparison_reliable' | 'ndwi_comparison_reliable' {
  if (index === 'ndre') return 'ndre_comparison_reliable'
  if (index === 'ndwi') return 'ndwi_comparison_reliable'
  return 'ndvi_comparison_reliable'
}

function fmt(value: string | null | undefined, digits = 3) {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return '—'
  return numeric.toLocaleString('sr-RS', { maximumFractionDigits: digits, signDisplay: 'auto' })
}

function fmtDelta(value: string | null | undefined) {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  if (Number.isNaN(numeric)) return '—'
  const text = numeric.toLocaleString('sr-RS', { maximumFractionDigits: 3, signDisplay: 'exceptZero' })
  return text
}

function pixelHint(point: SatelliteHistoryPoint, selected: IndexId[]) {
  if (!point.valid_pixel_counts) return ''
  const parts = selected
    .map((index) =>
      point.valid_pixel_counts?.[index] != null
        ? `${index.toUpperCase()} ${point.valid_pixel_counts[index]}`
        : null,
    )
    .filter(Boolean)
  return parts.length ? ` · validni pikseli ${parts.join(', ')}` : ''
}

function qualityLabel(quality: string) {
  if (quality === 'ok') return tr('uobičajena oblačnost')
  if (quality === 'elevated_cloud') return tr('povišena oblačnost')
  return tr('oblačnost nije sačuvana')
}

function relationLabel(relation: string) {
  if (relation === 'same_grid_cell') return tr('ista ćelija mreže')
  return 'potencijalno povezano'
}

export function SatelliteHistoryPanel({ parcelId }: { parcelId: string }) {
  const [selected, setSelected] = useState<IndexId[]>(['ndvi', 'ndre', 'ndwi'])
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const query = useQuery({
    queryKey: ['parcel-satellite-history', parcelId, dateFrom, dateTo],
    queryFn: () =>
      getParcelSatelliteHistory(parcelId, {
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
      }),
    enabled: Boolean(parcelId),
  })

  const data = query.data
  const points = data?.points ?? []

  function toggle(index: IndexId) {
    setSelected((current) => {
      if (current.includes(index)) {
        if (current.length === 1) return current
        return current.filter((item) => item !== index)
      }
      return [...current, index]
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Istorija indeksa</CardTitle>
        <p className="text-sm text-muted-foreground">
          {tr('Svaka tačka je sačuvani snimak. Linija samo spaja te datume — između njih nema merenja.')}
          Datum snimka nije datum obrade.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-wrap gap-1.5">
            {INDEXES.map((item) => {
              const on = selected.includes(item.id)
              return (
                <Button
                  key={item.id}
                  type="button"
                  size="sm"
                  variant={on ? 'default' : 'outline'}
                  onClick={() => toggle(item.id)}
                >
                  {item.label}
                </Button>
              )
            })}
          </div>
          <label className="text-xs text-muted-foreground">
            Od
            <input
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
              className="ml-2 h-9 rounded-lg border border-border bg-card px-2 text-sm text-foreground"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            Do
            <input
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
              className="ml-2 h-9 rounded-lg border border-border bg-card px-2 text-sm text-foreground"
            />
          </label>
          {dateFrom || dateTo ? (
            <Button type="button" size="sm" variant="outline" onClick={() => { setDateFrom(''); setDateTo('') }}>
              Ceo period
            </Button>
          ) : null}
        </div>

        {query.isLoading ? <p className="text-sm text-muted-foreground">{tr('Učitavanje istorije…')}</p> : null}
        {query.isError ? (
          <p className="text-sm text-danger">{tr('Istorija snimaka nije učitana.')}</p>
        ) : null}

        {data && data.earliest_acquisition_date ? (
          <p className="text-xs text-muted-foreground">
            {tr('Prvi sačuvani snimak: {{date}}', { date: data.earliest_acquisition_date })}
            {data.latest_acquisition_date
              ? tr(' · poslednji: {{date}}', { date: data.latest_acquisition_date })
              : ''}
            {data.truncated ? tr(' · prikazan je skraćen period') : ''}
          </p>
        ) : null}

        {data && points.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
            {data.earliest_acquisition_date
              ? tr('U izabranom periodu nema snimaka. Proširite datume ili izaberite ceo period.')
              : tr('Još nema sačuvane istorije. Posle prvog uspešnog snimka ovde će biti vremenska serija.')}
          </p>
        ) : null}

        {points.length > 0 ? (
          <IndexChart points={points} indexes={INDEXES.filter((item) => selected.includes(item.id))} />
        ) : null}

        {points.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="py-2 pr-2">Snimak</th>
                  <th className="py-2 pr-2">{tr('Obrađeno')}</th>
                  <th className="py-2 pr-2 text-right">{tr('Oblačnost')}</th>
                  {selected.map((index) => (
                    <th key={index} className="py-2 pr-2 text-right">
                      {index.toUpperCase()} / Δ
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {points.map((point) => (
                  <tr key={point.observation_id} className="border-b border-border/70 last:border-0">
                    <td className="py-2 pr-2 font-medium">{point.acquisition_date}</td>
                    <td className="py-2 pr-2 text-muted-foreground">
                      {point.processed_at
                        ? new Date(point.processed_at).toLocaleString('sr-RS')
                        : '—'}
                    </td>
                    <td className="py-2 pr-2 text-right">
                      {point.cloud_cover != null ? `${fmt(point.cloud_cover, 0)}%` : '—'}
                      <span className="mt-0.5 block text-[10px] text-muted-foreground">
                        {qualityLabel(point.quality)}
                        {pixelHint(point, selected)}
                      </span>
                    </td>
                    {selected.map((index) => {
                      const reliable = point[reliableKey(index)]
                      return (
                        <td key={index} className="py-2 pr-2 text-right font-mono">
                          {fmt(point[meanKey(index)])}
                          <span className="mt-0.5 block text-[11px] text-muted-foreground">
                            {fmtDelta(point[deltaKey(index)])}
                            {reliable === false ? ' · nepuzdano' : ''}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {data && data.repeated_anomalies.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">Ponovljene zone</p>
            <ul className="space-y-2">
              {data.repeated_anomalies.map((item) => (
                <li
                  key={`${item.zone_key}-${item.kind}-${item.index_name}`}
                  className="rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <p className="font-medium">
                    {item.zone_key ? zoneKeyLabel(item.zone_key) : tr('Zona bez ključa')} ·{' '}
                    {item.index_name.toUpperCase()} · {anomalyKindLabel(item.kind)}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    {relationLabel(item.relation)} · {item.occurrence_count} snimka (
                    {item.acquisition_dates.join(', ')})
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{item.note}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {data?.notes?.length ? (
          <ul className="space-y-1 text-xs text-muted-foreground">
            {data.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  )
}

function IndexChart({
  points,
  indexes,
}: {
  points: SatelliteHistoryPoint[]
  indexes: { id: IndexId; label: string; color: string }[]
}) {
  const layout = useMemo(() => {
    const width = 640
    const height = 220
    const pad = { l: 36, r: 12, t: 12, b: 28 }
    const values: number[] = []
    for (const point of points) {
      for (const index of indexes) {
        const raw = point[meanKey(index.id)]
        if (raw == null || raw === '') continue
        const numeric = Number(raw)
        if (!Number.isNaN(numeric)) values.push(numeric)
      }
    }
    if (values.length === 0) return null
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = max - min || 1
    const innerW = width - pad.l - pad.r
    const innerH = height - pad.t - pad.b
    const xAt = (index: number) =>
      points.length === 1 ? pad.l + innerW / 2 : pad.l + (index / (points.length - 1)) * innerW
    const yAt = (value: number) => pad.t + ((max - value) / span) * innerH
    const series = indexes.map((index) => {
      const dots = points.flatMap((point, indexOnAxis) => {
        const raw = point[meanKey(index.id)]
        if (raw == null || raw === '') return []
        const numeric = Number(raw)
        if (Number.isNaN(numeric)) return []
        return [{ x: xAt(indexOnAxis), y: yAt(numeric), date: point.acquisition_date }]
      })
      return { ...index, dots }
    })
    return { width, height, pad, min, max, series, xAt }
  }, [points, indexes])

  if (!layout) {
    return (
      <p className="text-sm text-muted-foreground">
        {tr('Izabrani indeksi nemaju sačuvanu vrednost u ovom periodu.')}
      </p>
    )
  }

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="h-56 w-full min-w-[20rem]"
        role="img"
        aria-label={tr('Vremenska serija satelitskih indeksa')}
      >
        <line
          x1={layout.pad.l}
          y1={layout.height - layout.pad.b}
          x2={layout.width - layout.pad.r}
          y2={layout.height - layout.pad.b}
          stroke="currentColor"
          strokeOpacity="0.2"
        />
        <text x={4} y={layout.pad.t + 4} fontSize="10" fill="currentColor" opacity="0.6">
          {layout.max.toFixed(2)}
        </text>
        <text x={4} y={layout.height - layout.pad.b} fontSize="10" fill="currentColor" opacity="0.6">
          {layout.min.toFixed(2)}
        </text>
        {layout.series.map((series) => (
          <g key={series.id}>
            {series.dots.length > 1 ? (
              <polyline
                fill="none"
                stroke={series.color}
                strokeWidth="2"
                points={series.dots.map((dot) => `${dot.x},${dot.y}`).join(' ')}
              />
            ) : null}
            {series.dots.map((dot) => (
              <circle key={`${series.id}-${dot.date}`} cx={dot.x} cy={dot.y} r="3.5" fill={series.color}>
                <title>
                  {series.label} {dot.date}
                </title>
              </circle>
            ))}
          </g>
        ))}
        {points.map((point, index) =>
          index === 0 || index === points.length - 1 || points.length <= 6 ? (
            <text
              key={point.observation_id}
              x={layout.xAt(index)}
              y={layout.height - 8}
              fontSize="10"
              textAnchor="middle"
              fill="currentColor"
              opacity="0.65"
            >
              {point.acquisition_date.slice(5)}
            </text>
          ) : null,
        )}
      </svg>
      <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {layout.series.map((series) => (
          <span key={series.id} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: series.color }} />
            {series.label}
          </span>
        ))}
      </div>
    </div>
  )
}
