import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getParcelWeather } from '@/features/orchard/api'
import { weatherIcon, weatherIconLabel } from '@/features/orchard/weatherIcons'
import {
  formatDayMonth,
  formatUpdatedAt,
  formatWeekday,
  isSameCalendarDay,
} from '@/shared/lib/format'
import { cn } from '@/shared/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'

const YR_SOURCE_URL = 'https://www.yr.no/'

export function ParcelWeatherForecast({ parcelId }: { parcelId: string }) {
  const weatherQuery = useQuery({
    queryKey: ['parcel-weather', parcelId],
    queryFn: () => getParcelWeather(parcelId),
    staleTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (weatherQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Vremenska prognoza</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 overflow-hidden">
            {Array.from({ length: 7 }).map((_, index) => (
              <div key={index} className="h-36 min-w-[4.5rem] flex-1 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (weatherQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Vremenska prognoza</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Vremenska prognoza trenutno nije dostupna.</p>
        </CardContent>
      </Card>
    )
  }

  const weather = weatherQuery.data
  if (!weather || weather.status === 'no_location' || weather.status === 'invalid_location') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Vremenska prognoza</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-sm font-medium">Vremenska prognoza nije dostupna</p>
          <p className="text-sm text-muted-foreground">
            {weather?.message || 'Za prikaz prognoze potrebno je da parcela ima definisanu lokaciju.'}
          </p>
          {weather?.status === 'invalid_location' ? (
            <Link to={`/orchard/${parcelId}/edit`} className="inline-flex text-sm font-medium text-primary hover:underline">
              Izmenite lokaciju parcele
            </Link>
          ) : null}
        </CardContent>
      </Card>
    )
  }

  if (!weather.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Vremenska prognoza</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">Vremenska prognoza trenutno nije dostupna.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <CardTitle>Vremenska prognoza</CardTitle>
          <p className="mt-2 text-sm font-medium">{weather.parcel_name}</p>
        </div>
        {weather.fetched_at ? (
          <p className="text-xs text-muted-foreground">Ažurirano: {formatUpdatedAt(weather.fetched_at)}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {weather.status === 'stale' ? (
          <p className="text-xs text-muted-foreground">
            Prikazani su poslednji dostupni podaci.
            {weather.fetched_at ? ` Poslednje ažuriranje: ${formatUpdatedAt(weather.fetched_at)}` : ''}
          </p>
        ) : null}
        <div className="overflow-x-auto">
          <div className="flex w-max gap-2 sm:grid sm:w-full sm:grid-cols-7">
            {weather.forecast.map((day) => {
              const today = isSameCalendarDay(day.date)
              const Icon = weatherIcon(day.symbol_code)
              return (
                <article
                  key={day.date}
                  className={cn(
                    'w-[5.25rem] shrink-0 rounded-xl border border-border bg-background px-2 py-3 text-center sm:w-auto',
                    today && 'border-primary bg-primary/5',
                  )}
                >
                  <p className="text-xs font-semibold capitalize">
                    {today ? 'Danas' : formatWeekday(day.date, true)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{formatDayMonth(day.date)}</p>
                  <Icon className="mx-auto mt-2 h-6 w-6 text-accent" aria-label={weatherIconLabel(day.symbol_code)} />
                  <p className="mt-2 text-sm font-semibold tabular-nums">{formatTemp(day.max_temperature)}</p>
                  <p className="text-xs text-muted-foreground tabular-nums">{formatTemp(day.min_temperature)}</p>
                  <p className="mt-2 text-[11px] text-muted-foreground">Kiša {formatPrecip(day.precipitation)}</p>
                  {day.precipitation_probability == null ? null : (
                    <p className="text-[11px] text-muted-foreground">{Math.round(day.precipitation_probability)}%</p>
                  )}
                </article>
              )
            })}
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Weather data by{' '}
          <a href={YR_SOURCE_URL} target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">
            Yr / MET Norway
          </a>
        </p>
      </CardContent>
    </Card>
  )
}

function formatTemp(value: number | null) {
  if (value == null || Number.isNaN(value)) return '—'
  return `${Math.round(value)}°`
}

function formatPrecip(value: number) {
  if (!Number.isFinite(value)) return '—'
  return `${value.toLocaleString('sr-Latn-RS', { maximumFractionDigits: 1 })} mm`
}
