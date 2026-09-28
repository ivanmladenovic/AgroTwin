import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getParcelSoilProfile, refreshParcelSoilProfile } from '@/features/orchard/api'
import type { ParcelSoilProfile, SoilProperty } from '@/shared/api/types'
import { formatUpdatedAt } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Select } from '@/shared/ui/select'

const SOILGRIDS_URL = 'https://www.isric.org/explore/soilgrids'
const DEFAULT_DEPTH = '30-60cm'

export function ParcelSoilCard({ parcelId }: { parcelId: string }) {
  const queryClient = useQueryClient()
  const [depth, setDepth] = useState<string>(DEFAULT_DEPTH)
  const [detailsOpen, setDetailsOpen] = useState(false)

  const soilQuery = useQuery({
    queryKey: ['parcel-soil', parcelId],
    queryFn: () => getParcelSoilProfile(parcelId),
    staleTime: 30 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshParcelSoilProfile(parcelId),
    onSuccess: (data) => {
      queryClient.setQueryData(['parcel-soil', parcelId], data)
    },
  })

  const profile = soilQuery.data
  const depthOptions = useMemo(() => collectDepths(profile), [profile])

  if (soilQuery.isLoading) {
    return (
      <Card>
        <SoilHeader parcelId={parcelId} />
        <CardContent className="space-y-3 px-4 py-3">
          <SoilAnalysesLink parcelId={parcelId} />
          <div className="h-16 animate-pulse rounded-lg bg-muted" />
        </CardContent>
      </Card>
    )
  }

  if (soilQuery.isError) {
    return (
      <Card>
        <SoilHeader parcelId={parcelId} />
        <CardContent className="space-y-3 px-4 py-3">
          <p className="text-xs text-muted-foreground">Podaci o zemljištu trenutno nisu dostupni.</p>
          <SoilAnalysesLink parcelId={parcelId} />
        </CardContent>
      </Card>
    )
  }

  if (!profile || profile.status === 'location_required') {
    return (
      <Card>
        <SoilHeader parcelId={parcelId} />
        <CardContent className="space-y-3 px-4 py-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">Lokacija parcele nije podešena.</p>
            <p className="text-xs text-muted-foreground">
              {profile?.message || 'Za prikaz modelovanih podataka o zemljištu unesite lokaciju parcele.'}
            </p>
            <Link to={`/orchard/${parcelId}/edit`} className="inline-flex text-xs font-medium text-primary hover:underline">
              Unesite lokaciju parcele
            </Link>
          </div>
          <SoilAnalysesLink parcelId={parcelId} />
        </CardContent>
      </Card>
    )
  }

  if (!profile.available) {
    return (
      <Card>
        <SoilHeader parcelId={parcelId} />
        <CardContent className="space-y-3 px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {profile.message || 'Podaci o zemljištu trenutno nisu dostupni.'}
          </p>
          <SoilAnalysesLink parcelId={parcelId} />
        </CardContent>
      </Card>
    )
  }

  const selectedDepth = resolveSelectedDepth(depth, depthOptions)

  return (
    <Card>
      <SoilHeader
        parcelId={parcelId}
        subtitle={profile.source_label}
        actions={
          <>
            {depthOptions.length > 1 ? (
              <Select
                value={selectedDepth}
                onChange={(event) => setDepth(event.target.value)}
                aria-label="Dubina profila"
                className="h-8 w-auto min-w-[6.5rem] px-2 py-0 text-xs lg:h-8 lg:text-xs"
              >
                {depthOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 px-2.5 text-xs"
              disabled={!profile.can_refresh || refreshMutation.isPending}
              onClick={() => refreshMutation.mutate()}
            >
              {refreshMutation.isPending ? 'Osvežavanje…' : 'Osveži'}
            </Button>
          </>
        }
      />
      <CardContent className="space-y-3 px-4 py-3">
        <SoilAnalysesLink parcelId={parcelId} />
        {profile.is_stale || profile.status === 'stale' || profile.status === 'partial' || profile.message ? (
          <p className="text-[11px] text-muted-foreground">{profile.message}</p>
        ) : null}
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 xl:grid-cols-7">
          {profile.properties.map((property) => {
            const atDepth = valueAtDepth(property, selectedDepth)
            return (
              <article key={property.key} className="rounded-lg border border-border bg-background px-2.5 py-1.5">
                <p className="text-[10px] font-medium leading-tight text-muted-foreground">{property.label}</p>
                <p className="mt-0.5 text-sm font-semibold leading-tight tabular-nums">
                  {atDepth ? formatSoilValue(atDepth.value, atDepth.unit || property.unit) : '—'}
                </p>
              </article>
            )
          })}
        </div>
        {detailsOpen ? <SoilDetailsTable properties={profile.properties} depths={depthOptions} /> : null}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          <button type="button" className="font-medium text-primary hover:underline" onClick={() => setDetailsOpen((open) => !open)}>
            {detailsOpen ? 'Sakrij detalje' : 'Prikaži detalje'}
          </button>
          <details>
            <summary className="cursor-pointer select-none">Šta znači modelovana procena?</summary>
            <p className="mt-1 max-w-2xl">{profile.source_explanation}</p>
          </details>
          {profile.fetched_at ? <span>Ažurirano: {formatUpdatedAt(profile.fetched_at)}</span> : null}
          <span className="sm:ml-auto">
            Izvor:{' '}
            <a href={SOILGRIDS_URL} target="_blank" rel="noreferrer" className="font-medium text-primary hover:underline">
              SoilGrids / ISRIC
            </a>
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function SoilAnalysesLink({ parcelId }: { parcelId: string }) {
  return (
    <Link to={`/orchard/${parcelId}/soil-analyses`} className="block">
      <Button type="button" variant="outline" size="sm" className="h-9 w-full justify-center text-xs sm:w-auto">
        Analize zemljišta
      </Button>
    </Link>
  )
}

function SoilHeader({
  parcelId: _parcelId,
  subtitle,
  actions,
}: {
  parcelId: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <CardHeader className="flex flex-col gap-2 space-y-0 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <CardTitle>Zemljište</CardTitle>
        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{subtitle || 'Modelovana procena – SoilGrids'}</p>
      </div>
      {actions ? <div className="flex flex-none flex-wrap items-center gap-1.5">{actions}</div> : null}
    </CardHeader>
  )
}

function SoilDetailsTable({
  properties,
  depths,
}: {
  properties: SoilProperty[]
  depths: { value: string; label: string }[]
}) {
  return (
    <div className="space-y-3">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[36rem] text-left text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-medium">Dubina</th>
              {properties.map((property) => (
                <th key={property.key} className="py-1 pr-3 font-medium">
                  {property.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {depths.map((depth) => (
              <tr key={depth.value} className="border-t border-border">
                <td className="py-1.5 pr-3">{depth.label}</td>
                {properties.map((property) => {
                  const value = valueAtDepth(property, depth.value)
                  return (
                    <td key={property.key} className="py-1.5 pr-3 tabular-nums">
                      {value ? formatSoilValue(value.value, value.unit || property.unit) : 'Nema podataka'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 md:hidden">
        {depths.map((depth) => (
          <article key={depth.value} className="rounded-xl border border-border bg-background px-4 py-3">
            <p className="text-xs font-medium text-muted-foreground">{depth.label}</p>
            <dl className="mt-2 space-y-1 text-sm">
              {properties.map((property) => {
                const value = valueAtDepth(property, depth.value)
                return (
                  <div key={property.key} className="flex items-baseline justify-between gap-3">
                    <dt className="text-muted-foreground">{property.label}</dt>
                    <dd className="tabular-nums">
                      {value ? formatSoilValue(value.value, value.unit || property.unit) : 'Nema podataka'}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </article>
        ))}
      </div>
    </div>
  )
}

function collectDepths(profile: ParcelSoilProfile | undefined) {
  const seen = new Map<string, string>()
  for (const key of profile?.depths ?? []) {
    seen.set(key, depthLabelFromKey(key, profile?.properties ?? []))
  }
  for (const property of profile?.properties ?? []) {
    for (const item of property.depths) {
      if (!seen.has(item.depth)) seen.set(item.depth, item.depth_label)
    }
  }
  return Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
}

function depthLabelFromKey(depth: string, properties: SoilProperty[]) {
  for (const property of properties) {
    const match = property.depths.find((item) => item.depth === depth)
    if (match) return match.depth_label
  }
  return depth.replace('cm', ' cm').replace('-', '–')
}

function resolveSelectedDepth(depth: string, options: { value: string; label: string }[]) {
  if (options.some((item) => item.value === depth)) return depth
  if (options.some((item) => item.value === DEFAULT_DEPTH)) return DEFAULT_DEPTH
  return options[0]?.value
}

function valueAtDepth(property: SoilProperty, depth: string | undefined) {
  if (!depth) return property.depths[0]
  return property.depths.find((item) => item.depth === depth)
}

function formatSoilValue(value: number, unit: string) {
  const formatted = value.toLocaleString('sr-Latn-RS', { maximumFractionDigits: 2 })
  return unit ? `${formatted} ${unit}` : formatted
}
