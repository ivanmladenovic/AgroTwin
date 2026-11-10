import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createEnterpriseOtkupPurchase,
  deleteEnterpriseOtkupPurchase,
  getEnterpriseOtkupOverview,
  listEnterpriseOtkupPurchases,
  upsertEnterpriseOtkupPrice,
} from '@/features/enterprise/api'
import { formatNumber } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Select } from '@/shared/ui/select'
import type {
  EnterpriseOtkupSupplierRow,
  EnterprisePurchaseCurrency,
  EnterpriseQuantityBasis,
} from '@/shared/api/types'

import { tr } from '@/shared/i18n/i18n'
export function EnterpriseOtkupTab({
  organizationId,
  canWrite,
}: {
  organizationId: string
  canWrite: boolean
}) {
  useTranslation()
  const yearNow = new Date().getFullYear()
  const [year, setYear] = useState(String(yearNow))
  const seasonYear = Number(year) || yearNow
  const queryClient = useQueryClient()

  const overviewQuery = useQuery({
    queryKey: ['enterprise-otkup', organizationId, seasonYear],
    queryFn: () => getEnterpriseOtkupOverview(organizationId, seasonYear),
  })
  const purchasesQuery = useQuery({
    queryKey: ['enterprise-otkup-purchases', organizationId, seasonYear],
    queryFn: () => listEnterpriseOtkupPurchases(organizationId, { year: seasonYear }),
  })

  const overview = overviewQuery.data
  const suppliers = overview?.suppliers ?? []

  const [priceFarmId, setPriceFarmId] = useState('')
  const [currency, setCurrency] = useState<EnterprisePurchaseCurrency>('RSD')
  const [priceBruto, setPriceBruto] = useState('')
  const [priceNeto, setPriceNeto] = useState('')
  const [priceNotes, setPriceNotes] = useState('')

  const [purchaseFarmId, setPurchaseFarmId] = useState('')
  const [purchasedOn, setPurchasedOn] = useState(new Date().toISOString().slice(0, 10))
  const [quantityKg, setQuantityKg] = useState('')
  const [basis, setBasis] = useState<EnterpriseQuantityBasis>('bruto')
  const [unitPrice, setUnitPrice] = useState('')
  const [purchaseNotes, setPurchaseNotes] = useState('')

  const selectedSupplier = useMemo(
    () => suppliers.find((s) => s.farm_id === purchaseFarmId),
    [suppliers, purchaseFarmId],
  )

  const suggestedUnitPrice = useMemo(() => {
    if (!selectedSupplier) return ''
    const raw =
      basis === 'bruto' ? selectedSupplier.price_bruto_per_kg : selectedSupplier.price_neto_per_kg
    return raw ?? ''
  }, [selectedSupplier, basis])

  function loadPriceForm(row: EnterpriseOtkupSupplierRow) {
    setPriceFarmId(row.farm_id)
    setCurrency(row.currency ?? 'RSD')
    setPriceBruto(row.price_bruto_per_kg ?? '')
    setPriceNeto(row.price_neto_per_kg ?? '')
    setPriceNotes(row.price_notes ?? '')
  }

  const savePrice = useMutation({
    mutationFn: () =>
      upsertEnterpriseOtkupPrice(organizationId, {
        farm_id: priceFarmId,
        season_year: seasonYear,
        currency,
        price_bruto_per_kg: priceBruto || null,
        price_neto_per_kg: priceNeto || null,
        notes: priceNotes || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-otkup', organizationId] })
    },
  })

  const createPurchase = useMutation({
    mutationFn: () =>
      createEnterpriseOtkupPurchase(organizationId, {
        farm_id: purchaseFarmId,
        purchased_on: purchasedOn,
        quantity_kg: quantityKg,
        quantity_basis: basis,
        currency: selectedSupplier?.currency ?? currency,
        unit_price_per_kg: unitPrice || suggestedUnitPrice || null,
        notes: purchaseNotes || null,
      }),
    onSuccess: async () => {
      setQuantityKg('')
      setUnitPrice('')
      setPurchaseNotes('')
      await queryClient.invalidateQueries({ queryKey: ['enterprise-otkup', organizationId] })
      await queryClient.invalidateQueries({
        queryKey: ['enterprise-otkup-purchases', organizationId],
      })
    },
  })

  const removePurchase = useMutation({
    mutationFn: (purchaseId: string) => deleteEnterpriseOtkupPurchase(organizationId, purchaseId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['enterprise-otkup', organizationId] })
      await queryClient.invalidateQueries({
        queryKey: ['enterprise-otkup-purchases', organizationId],
      })
    },
  })

  const totalsLabel = useMemo(() => {
    const entries = Object.entries(overview?.totals_by_currency ?? {})
    if (entries.length === 0) return '—'
    return entries.map(([cur, amt]) => `${formatNumber(amt)} ${cur}`).join(' · ')
  }, [overview?.totals_by_currency])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">{tr('Berba i otkup po dobavljačima')}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {tr(
              'Pregled koliko je lešnika prikupljeno (berba sa dodeljenih parcela), zatim cene i evidencija otkupa.',
            )}
          </p>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{tr("Sezona")}</label>
          <Input className="w-28" type="number" value={year} onChange={(e) => setYear(e.target.value)} />
        </div>
      </div>

      {(overview?.notes ?? []).map((note) => (
        <p key={note} className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm">
          {note}
        </p>
      ))}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={tr("Dobavljači")} value={formatNumber(suppliers.length)} />
        <Stat
          label={tr('Sa berbom')}
          value={`${formatNumber(overview?.suppliers_with_harvest ?? 0)} / ${formatNumber(suppliers.length)}`}
        />
        <Stat
          label={tr("Berba neto")}
          value={
            overview?.harvest_net_kg != null
              ? `${formatNumber(overview.harvest_net_kg)} kg`
              : tr('Nije dostupno')
          }
        />
        <Stat
          label={tr("Berba bruto")}
          value={
            overview?.harvest_gross_kg != null
              ? `${formatNumber(overview.harvest_gross_kg)} kg`
              : tr('Nije dostupno')
          }
        />
      </div>

      <section className="overflow-hidden rounded-2xl border border-border">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold">{tr('Pregled berbe po dobavljaču')}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {tr(
              'Zbir berbi koje su proizvođači evidentirali na dodeljenim parcelama u sezoni {{year}}. Nedostajuća berba nije prikazana kao nula.',
              { year: seasonYear },
            )}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5">{tr("Dobavljač")}</th>
                <th className="px-4 py-2.5">{tr('Parcele')}</th>
                <th className="px-4 py-2.5">{tr('Unosi berbe')}</th>
                <th className="px-4 py-2.5">Bruto</th>
                <th className="px-4 py-2.5">Neto</th>
                <th className="px-4 py-2.5">{tr("Poslednja berba")}</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((row) => (
                <tr key={row.farm_id} className="border-b border-border/70">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">{row.producer_display_name || row.farm_name}</p>
                    {row.producer_display_name && row.farm_name !== row.producer_display_name ? (
                      <p className="text-xs text-muted-foreground">{row.farm_name}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatNumber(row.parcels_with_harvest)} / {formatNumber(row.assigned_parcels)}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {row.harvest_event_count > 0 ? formatNumber(row.harvest_event_count) : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {row.harvest_gross_kg != null
                      ? `${formatNumber(row.harvest_gross_kg)} kg`
                      : tr('Nije dostupno')}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums font-medium text-primary">
                    {row.harvest_net_kg != null
                      ? `${formatNumber(row.harvest_net_kg)} kg`
                      : tr('Nije dostupno')}
                  </td>
                  <td className="px-4 py-2.5">{row.last_harvested_on ?? '—'}</td>
                </tr>
              ))}
              {suppliers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-muted-foreground">
                    {tr('Nema povezanih dobavljača.')}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label={tr("Otkupi (sezona)")} value={formatNumber(overview?.purchase_count ?? 0)} />
        <Stat
          label="Otkupljeno"
          value={
            overview?.purchased_quantity_kg != null
              ? `${formatNumber(overview.purchased_quantity_kg)} kg`
              : overview?.total_quantity_kg != null
                ? `${formatNumber(overview.total_quantity_kg)} kg`
                : '—'
          }
        />
        <Stat label="Iznos otkupa" value={totalsLabel} />
      </div>

      <section className="overflow-hidden rounded-2xl border border-border">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold">Cene i otkup</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {tr('Definisane cene i evidentirani otkupi Enterprise-a (nije isto što i berba proizvođača).')}
            {tr('Klik na „Cena“ učitava formu.')}
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5">{tr("Dobavljač")}</th>
                <th className="px-4 py-2.5">Valuta</th>
                <th className="px-4 py-2.5">Bruto / kg</th>
                <th className="px-4 py-2.5">Neto / kg</th>
                <th className="px-4 py-2.5">Otkupi</th>
                <th className="px-4 py-2.5">Otkupljeno</th>
                <th className="px-4 py-2.5">Iznos*</th>
                <th className="px-4 py-2.5">Poslednji</th>
                {canWrite ? <th className="px-4 py-2.5" /> : null}
              </tr>
            </thead>
            <tbody>
              {suppliers.map((row) => (
                <tr key={`price-${row.farm_id}`} className="border-b border-border/70">
                  <td className="px-4 py-2.5">
                    <p className="font-medium">{row.producer_display_name || row.farm_name}</p>
                  </td>
                  <td className="px-4 py-2.5">{row.currency ?? '—'}</td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {row.price_bruto_per_kg != null ? formatNumber(row.price_bruto_per_kg) : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {row.price_neto_per_kg != null ? formatNumber(row.price_neto_per_kg) : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{formatNumber(row.purchase_count)}</td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {(row.purchased_quantity_kg ?? row.total_quantity_kg) != null
                      ? `${formatNumber(row.purchased_quantity_kg ?? row.total_quantity_kg)} kg`
                      : '—'}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {(row.purchased_amount ?? row.total_amount) != null
                      ? formatNumber(row.purchased_amount ?? row.total_amount)
                      : '—'}
                  </td>
                  <td className="px-4 py-2.5">{row.last_purchased_on ?? '—'}</td>
                  {canWrite ? (
                    <td className="px-4 py-2.5">
                      <Button type="button" variant="outline" size="sm" onClick={() => loadPriceForm(row)}>
                        Cena
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
              {suppliers.length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 9 : 8} className="px-4 py-8 text-muted-foreground">
                    {tr('Nema povezanih dobavljača.')}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <p className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          {tr('* Iznos po dobavljaču sabira otkupe u njihovoj valuti evidencije; mešovite valute nisu')}
          zbrajane u jednu sumu.
        </p>
      </section>

      {canWrite ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="space-y-3 rounded-2xl border border-border p-4">
            <h3 className="text-sm font-semibold">{tr('Cena po kg')}</h3>
            <p className="text-xs text-muted-foreground">
              {tr('Definišite bruto i/ili neto cenu za dobavljača u sezoni {{year}}.', {
                year: seasonYear,
              })}
            </p>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">{tr("Dobavljač")}</label>
              <Select value={priceFarmId} onChange={(e) => setPriceFarmId(e.target.value)}>
                <option value="">{tr('Izaberi…')}</option>
                {suppliers.map((s) => (
                  <option key={s.farm_id} value={s.farm_id}>
                    {s.producer_display_name || s.farm_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Valuta</label>
                <Select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value as EnterprisePurchaseCurrency)}
                >
                  <option value="RSD">RSD</option>
                  <option value="EUR">EUR</option>
                </Select>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Bruto / kg</label>
                <Input value={priceBruto} onChange={(e) => setPriceBruto(e.target.value)} inputMode="decimal" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Neto / kg</label>
                <Input value={priceNeto} onChange={(e) => setPriceNeto(e.target.value)} inputMode="decimal" />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Napomena</label>
              <Input value={priceNotes} onChange={(e) => setPriceNotes(e.target.value)} />
            </div>
            <Button
              type="button"
              disabled={!priceFarmId || savePrice.isPending}
              onClick={() => savePrice.mutate()}
            >
              {tr('Sačuvaj cenu')}
            </Button>
            {savePrice.isError ? (
              <p className="text-sm text-danger">{tr('Čuvanje cene nije uspelo.')}</p>
            ) : null}
          </section>

          <section className="space-y-3 rounded-2xl border border-border p-4">
            <h3 className="text-sm font-semibold">Novi otkup</h3>
            <p className="text-xs text-muted-foreground">
              {tr(
                'Beleži izvršeni otkup. Ako je cena definisana, predlaže se automatski; može se pregaziti.',
              )}
            </p>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">{tr("Dobavljač")}</label>
              <Select
                value={purchaseFarmId}
                onChange={(e) => {
                  setPurchaseFarmId(e.target.value)
                  setUnitPrice('')
                }}
              >
                <option value="">{tr('Izaberi…')}</option>
                {suppliers.map((s) => (
                  <option key={s.farm_id} value={s.farm_id}>
                    {s.producer_display_name || s.farm_name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Datum</label>
                <Input type="date" value={purchasedOn} onChange={(e) => setPurchasedOn(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Osnova</label>
                <Select
                  value={basis}
                  onChange={(e) => {
                    setBasis(e.target.value as EnterpriseQuantityBasis)
                    setUnitPrice('')
                  }}
                >
                  <option value="bruto">Bruto</option>
                  <option value="neto">Neto</option>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">{tr('Količina (kg)')}</label>
                <Input value={quantityKg} onChange={(e) => setQuantityKg(e.target.value)} inputMode="decimal" />
              </div>
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">
                  Cena / kg{suggestedUnitPrice ? ` (predlog ${formatNumber(suggestedUnitPrice)})` : ''}
                </label>
                <Input
                  value={unitPrice}
                  placeholder={suggestedUnitPrice || undefined}
                  onChange={(e) => setUnitPrice(e.target.value)}
                  inputMode="decimal"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Napomena</label>
              <Input value={purchaseNotes} onChange={(e) => setPurchaseNotes(e.target.value)} />
            </div>
            <Button
              type="button"
              disabled={!purchaseFarmId || !quantityKg || createPurchase.isPending}
              onClick={() => createPurchase.mutate()}
            >
              {tr('Sačuvaj otkup')}
            </Button>
            {createPurchase.isError ? (
              <p className="text-sm text-danger">
                {(createPurchase.error as Error)?.message || tr('Čuvanje otkupa nije uspelo.')}
              </p>
            ) : null}
          </section>
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
          {tr('Pregled je dostupan. Unos cena i otkupa zahteva ulogu administratora ili analitičara.')}
        </p>
      )}

      <section className="overflow-hidden rounded-2xl border border-border">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold">Evidencija otkupa · {seasonYear}</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5">Datum</th>
                <th className="px-4 py-2.5">{tr("Dobavljač")}</th>
                <th className="px-4 py-2.5">Osnova</th>
                <th className="px-4 py-2.5">{tr("Količina")}</th>
                <th className="px-4 py-2.5">Cena / kg</th>
                <th className="px-4 py-2.5">Iznos</th>
                <th className="px-4 py-2.5">Napomena</th>
                {canWrite ? <th className="px-4 py-2.5" /> : null}
              </tr>
            </thead>
            <tbody>
              {(purchasesQuery.data ?? []).map((row) => (
                <tr key={row.id} className="border-b border-border/70">
                  <td className="px-4 py-2.5">{row.purchased_on}</td>
                  <td className="px-4 py-2.5 font-medium">
                    {row.producer_display_name || row.farm_name || '—'}
                  </td>
                  <td className="px-4 py-2.5 capitalize">{row.quantity_basis}</td>
                  <td className="px-4 py-2.5 tabular-nums">{formatNumber(row.quantity_kg)} kg</td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {formatNumber(row.unit_price_per_kg)} {row.currency}
                  </td>
                  <td className="px-4 py-2.5 tabular-nums font-medium">
                    {formatNumber(row.total_amount)} {row.currency}
                  </td>
                  <td className="px-4 py-2.5 text-muted-foreground">{row.notes || '—'}</td>
                  {canWrite ? (
                    <td className="px-4 py-2.5">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={removePurchase.isPending}
                        onClick={() => {
                          if (window.confirm(tr('Obrisati ovaj otkup?'))) removePurchase.mutate(row.id)
                        }}
                      >
                        {tr("Obriši")}
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
              {(purchasesQuery.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={canWrite ? 8 : 7} className="px-4 py-8 text-muted-foreground">
                    Nema evidentiranih otkupa za {seasonYear}.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  )
}
