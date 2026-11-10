import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchCompliancePackage,
  listComplianceDefinitions,
  listComplianceRuns,
} from '@/features/compliance/api'
import { listParcels } from '@/features/orchard/api'
import type { ComplianceReportType } from '@/shared/api/types'
import { formatDate } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'

import { tr } from '@/shared/i18n/i18n'
function reportTypeLabels(): Record<ComplianceReportType, string> {
  return {
  farm_profile: tr('01 Profil gazdinstva'),
  parcel_register: tr('02 Registar parcela'),
  plant_protection: tr('03 Zaštita bilja'),
  fertilization_inputs: tr('04 Đubrenje i unosi'),
  harvest_traceability: tr('05 Berba i sledljivost'),
  farm_activity: tr('06 Aktivnosti na gazdinstvu'),
  irrigation_water: tr('07 Navodnjavanje i voda'),
  compliance_package: tr('Paket usaglašenosti / audita'),
  }
}

const FORMAT_LABELS: Record<string, string> = {
  json: 'JSON',
  csv: 'CSV',
  pdf: 'PDF',
  zip: 'ZIP',
}

export function CompliancePage() {
  const queryClient = useQueryClient()
  const year = new Date().getFullYear()
  const [dateFrom, setDateFrom] = useState(`${year}-01-01`)
  const [dateTo, setDateTo] = useState(`${year}-12-31`)
  const [parcelId, setParcelId] = useState('')
  const [packageTypes, setPackageTypes] = useState<ComplianceReportType[]>([
    'farm_profile',
    'parcel_register',
    'plant_protection',
    'fertilization_inputs',
    'harvest_traceability',
    'farm_activity',
    'irrigation_water',
  ])
  const [error, setError] = useState<string | null>(null)

  const parcelsQuery = useQuery({ queryKey: ['parcels'], queryFn: listParcels })
  const definitionsQuery = useQuery({ queryKey: ['compliance-definitions'], queryFn: listComplianceDefinitions })
  const runsQuery = useQuery({ queryKey: ['compliance-runs'], queryFn: listComplianceRuns })

  const packageMutation = useMutation({
    mutationFn: () =>
      fetchCompliancePackage({
        date_from: dateFrom || null,
        date_to: dateTo || null,
        parcel_ids: parcelId ? [parcelId] : [],
        report_types: packageTypes,
        include_costs: true,
        as_zip: true,
      }),
    onSuccess: async (blob) => {
      setError(null)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `agrotwin-compliance-package-${dateFrom || 'all'}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      await queryClient.invalidateQueries({ queryKey: ['compliance-runs'] })
    },
    onError: (err: Error) => setError(err.message),
  })

  const definitions = useMemo(
    () =>
      (definitionsQuery.data ?? [])
        .filter((item) => item.type !== 'compliance_package')
        .sort((a, b) => a.sort_order - b.sort_order || a.title.localeCompare(b.title, 'sr')),
    [definitionsQuery.data],
  )
  const parcels = parcelsQuery.data ?? []
  const runs = runsQuery.data ?? []

  const typeLabelByKey = useMemo(() => {
    const map: Partial<Record<ComplianceReportType, string>> = { ...reportTypeLabels() }
    for (const def of definitions) {
      map[def.type] = def.title
    }
    return map
  }, [definitions])

  function togglePackageType(type: ComplianceReportType) {
    setPackageTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    )
  }

  function reportTypeLabel(type: string) {
    return typeLabelByKey[type as ComplianceReportType] ?? type
  }

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{tr('Usaglašenost i izveštaji')}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          {tr(
            tr('Generišite paket PDF izveštaja iz evidencije u AgroTwin. Modul ne sertifikuje gazdinstvo i ne garantuje usklađenost sa GLOBALG.A.P. ili drugim standardima.'),
          )}
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filteri</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Od</Label>
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>Do</Label>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label>{tr("Parcela")}</Label>
            <Select value={parcelId} onChange={(e) => setParcelId(e.target.value)}>
              <option value="">{tr('Sve parcele')}</option>
              {parcels.map((parcel) => (
                <option key={parcel.id} value={parcel.id}>
                  {parcel.name}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{tr('Segmenti izveštaja')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {tr('Izaberite koje PDF izveštaje (01–07) želite u ZIP paketu.')}
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {definitions.map((def) => (
              <label
                key={def.id}
                className="flex items-start gap-2 rounded-lg border border-border/70 px-3 py-2.5 text-sm hover:bg-muted/30"
              >
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={packageTypes.includes(def.type)}
                  onChange={() => togglePackageType(def.type)}
                />
                <span>
                  <span className="font-medium">{def.title}</span>
                  <span className="block text-xs text-muted-foreground">{def.description}</span>
                </span>
              </label>
            ))}
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <Button
            disabled={packageMutation.isPending || packageTypes.length === 0}
            onClick={() => packageMutation.mutate()}
          >
            {packageMutation.isPending ? tr('Generisanje…') : tr('Generiši paket PDF izveštaja (ZIP)')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{tr('Istorija generisanja')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {runsQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">{tr('Učitavanje…')}</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">{tr('Još nema generisanih izveštaja.')}</p>
          ) : (
            runs.slice(0, 20).map((run) => (
              <div
                key={run.id}
                className="flex flex-wrap items-center justify-between gap-2 border-b border-border py-2 text-sm last:border-0"
              >
                <div>
                  <p className="font-medium">{run.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(run.created_at.slice(0, 10))} · {FORMAT_LABELS[run.format] ?? run.format} ·{' '}
                    {run.record_count} zapisa
                  </p>
                </div>
                <p className="text-xs font-medium text-muted-foreground">
                  {reportTypeLabel(run.report_type)}
                </p>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )
}
