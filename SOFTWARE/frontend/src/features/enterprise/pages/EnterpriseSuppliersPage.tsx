import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Building2, MapPin, Trees } from 'lucide-react'

import { listEnterpriseSuppliers } from '@/features/enterprise/api'
import { useEnterprise } from '@/features/enterprise/EnterpriseContext'
import { formatNumber } from '@/shared/lib/format'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import { cn } from '@/shared/lib/utils'

import { tr } from '@/shared/i18n/i18n'

const STATUS_LABEL_KEYS: Record<string, string> = {
  active: 'Aktivan',
  inactive: 'Neaktivan',
  pending: 'Na čekanju',
}

export function EnterpriseSuppliersPage() {
  useTranslation()
  const { organizationId } = useEnterprise()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const query = useQuery({
    queryKey: ['enterprise-suppliers', organizationId, q, status],
    queryFn: () =>
      listEnterpriseSuppliers(organizationId, {
        q: q || undefined,
        status: status || undefined,
      }),
  })

  return (
    <div className="space-y-6">
      <div>
        <p className="kicker">{tr("Dobavljači")}</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{tr('Mreža dobavljača')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {tr(
            'Prikaz po imenu / firmi na koju se vodi nalog. Operativni podaci proizvođača su samo za čitanje.',
          )}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <Input
          placeholder={tr('Pretraga po imenu, firmi ili kodu')}
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        <Select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">{tr('Svi statusi')}</option>
          <option value="active">{tr("Aktivan")}</option>
          <option value="inactive">Neaktivan</option>
          <option value="pending">{tr("Na čekanju")}</option>
        </Select>
      </div>

      {query.isLoading ? (
        <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {(query.data ?? []).map((item) => {
            const title =
              item.producer_display_name || item.owner_full_name || item.farm_name || item.farm_id
            return (
              <Link
                key={item.id}
                to={`/enterprise/${organizationId}/suppliers/${item.id}`}
                className="group flex flex-col rounded-2xl border border-border/80 bg-card p-4 shadow-sm transition hover:border-primary/35 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-lg font-semibold tracking-tight group-hover:text-primary">
                      {title}
                    </p>
                    {item.farm_name && item.farm_name !== title ? (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        Zasad: {item.farm_name}
                      </p>
                    ) : null}
                  </div>
                  <span
                    className={cn(
                      'shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold',
                      item.status === 'active'
                        ? 'bg-emerald-100 text-emerald-800'
                        : item.status === 'pending'
                          ? 'bg-amber-100 text-amber-900'
                          : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {tr(STATUS_LABEL_KEYS[item.status] ?? item.status)}
                  </span>
                </div>

                {item.farm_location ? (
                  <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    {item.farm_location}
                  </p>
                ) : null}

                <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-xl bg-muted/40 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Parcele
                    </p>
                    <p className="mt-0.5 font-semibold tabular-nums">
                      {formatNumber(item.assigned_parcel_count)}
                    </p>
                  </div>
                  <div className="rounded-xl bg-muted/40 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {tr("Površina")}
                    </p>
                    <p className="mt-0.5 font-semibold tabular-nums">
                      {item.assigned_area_ha != null
                        ? `${formatNumber(item.assigned_area_ha)} ha`
                        : '—'}
                    </p>
                  </div>
                  <div className="rounded-xl bg-muted/40 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {tr("Očekivano")}
                    </p>
                    <p className="mt-0.5 font-semibold tabular-nums">
                      {item.expected_yield_kg != null
                        ? `${formatNumber(item.expected_yield_kg)} kg`
                        : '—'}
                    </p>
                  </div>
                  <div className="rounded-xl bg-muted/40 px-3 py-2">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {tr("Ostvareno")}
                    </p>
                    <p className="mt-0.5 font-semibold tabular-nums">
                      {item.actual_yield_kg != null
                        ? `${formatNumber(item.actual_yield_kg)} kg`
                        : '—'}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-2 border-t border-border/60 pt-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5" />
                    {item.internal_code ? `Kod ${item.internal_code}` : tr('Bez internog koda')}
                  </span>
                  {item.completeness_avg != null ? (
                    <span className="inline-flex items-center gap-1">
                      <Trees className="h-3.5 w-3.5" />
                      Podaci {formatNumber(item.completeness_avg)}%
                    </span>
                  ) : null}
                </div>
              </Link>
            )
          })}
          {(query.data ?? []).length === 0 ? (
            <p className="col-span-full rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {tr('Nema dobavljača za prikaz.')}
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}
