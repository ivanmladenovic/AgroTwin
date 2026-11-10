import { useMutation } from '@tanstack/react-query'
import { AlertTriangle, Check, Eye, Plus, X } from 'lucide-react'
import { useState } from 'react'

import {
  addSoilAnalysisResult,
  openSoilAnalysis,
  skipSoilAnalysis,
  updateSoilAnalysisResult,
  verifySoilAnalysis,
} from '@/features/journal/api'
import type { SoilLabAnalysis, SoilLabResult } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'

import { tr } from '@/shared/i18n/i18n'
const PARAMETER_OPTIONS = [
  { code: 'PH', label: 'pH' },
  { code: 'HUMUS', label: 'Humus' },
  { code: 'ORGANIC_CARBON', label: 'Organski ugljenik' },
  { code: 'TOTAL_N', label: tr('Ukupan N') },
  { code: 'AVAILABLE_P', label: tr('Pristupačan P') },
  { code: 'AVAILABLE_K', label: tr('Pristupačan K') },
  { code: 'CA', label: 'Kalcijum' },
  { code: 'MG', label: 'Magnezijum' },
  { code: 'S', label: 'Sumpor' },
  { code: 'FE', label: tr('Gvožđe') },
  { code: 'ZN', label: 'Cink' },
  { code: 'B', label: 'Bor' },
  { code: 'MN', label: 'Mangan' },
  { code: 'CU', label: 'Bakar' },
  { code: 'CEC', label: 'CEC' },
  { code: 'TEXTURE', label: 'Tekstura' },
  { code: 'SAND', label: 'Pesak' },
  { code: 'SILT', label: tr('Prašina') },
  { code: 'CLAY', label: 'Glina' },
]

export function SoilLabReviewPanel({
  analysis,
  onUpdated,
  onClose,
}: {
  analysis: SoilLabAnalysis
  onUpdated: (next: SoilLabAnalysis) => void
  onClose?: () => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState({ value: '', unit: '', original_parameter_name: '' })
  const [adding, setAdding] = useState(false)
  const [addDraft, setAddDraft] = useState({
    parameter_code: 'PH',
    original_parameter_name: '',
    value: '',
    unit: '',
  })
  const [sourcePreview, setSourcePreview] = useState<SoilLabResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const verifyMutation = useMutation({
    mutationFn: () => verifySoilAnalysis(analysis.id),
    onSuccess: onUpdated,
    onError: (err) => setError(err instanceof Error ? err.message : tr('Potvrda nije uspela')),
  })
  const skipMutation = useMutation({
    mutationFn: () => skipSoilAnalysis(analysis.id),
    onSuccess: onUpdated,
    onError: (err) => setError(err instanceof Error ? err.message : tr('Preskakanje nije uspelo')),
  })
  const updateMutation = useMutation({
    mutationFn: () =>
      updateSoilAnalysisResult(analysis.id, editingId!, {
        value: draft.value,
        unit: draft.unit || null,
        original_parameter_name: draft.original_parameter_name,
      }),
    onSuccess: (next) => {
      setEditingId(null)
      onUpdated(next)
    },
    onError: (err) => setError(err instanceof Error ? err.message : tr('Izmena nije uspela')),
  })
  const addMutation = useMutation({
    mutationFn: () =>
      addSoilAnalysisResult(analysis.id, {
        parameter_code: addDraft.parameter_code,
        original_parameter_name: addDraft.original_parameter_name || addDraft.parameter_code,
        value: addDraft.value,
        unit: addDraft.unit || null,
      }),
    onSuccess: (next) => {
      setAdding(false)
      setAddDraft({ parameter_code: 'PH', original_parameter_name: '', value: '', unit: '' })
      onUpdated(next)
    },
    onError: (err) => setError(err instanceof Error ? err.message : tr('Dodavanje nije uspelo')),
  })

  const busy = verifyMutation.isPending || skipMutation.isPending || updateMutation.isPending || addMutation.isPending
  const results = analysis.results ?? []

  return (
    <Card className="border-primary/30">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Laboratorijska analiza</p>
          <CardTitle className="mt-1">{tr('Analiza je obrađena.')}</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            {tr('Proverite izdvojene parametre. Visoka pouzdanost je unapred označena; ostalo zahteva potvrdu.')}
            Vrednosti se nikad ne menjaju tiho.
          </p>
        </div>
        {onClose ? (
          <Button type="button" variant="ghost" size="sm" onClick={onClose} aria-label={tr('Zatvori')}>
            <X className="h-4 w-4" />
          </Button>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Parametar</th>
                <th className="px-3 py-2 font-medium">Vrednost</th>
                <th className="px-3 py-2 font-medium">Jedinica</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {results.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-3 py-4 text-sm text-muted-foreground">
                    {tr('Nisu automatski prepoznati parametri. Dodajte ih ručno ili otvorite PDF.')}
                    {analysis.extraction_error
                      ? tr(' Greška: {{message}}', { message: analysis.extraction_error })
                      : ''}
                  </td>
                </tr>
              ) : (
                results.map((result) => {
                  const ok = result.high_confidence || result.verification_status === 'verified'
                  const editing = editingId === result.id
                  return (
                    <tr key={result.id} className="border-t border-border">
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input
                            value={draft.original_parameter_name}
                            onChange={(event) =>
                              setDraft((prev) => ({ ...prev, original_parameter_name: event.target.value }))
                            }
                          />
                        ) : (
                          <div>
                            <p className="font-medium">{result.original_parameter_name}</p>
                            <p className="text-[11px] text-muted-foreground">{result.parameter_code}</p>
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input
                            value={draft.value}
                            onChange={(event) => setDraft((prev) => ({ ...prev, value: event.target.value }))}
                          />
                        ) : (
                          result.value
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {editing ? (
                          <Input
                            value={draft.unit}
                            onChange={(event) => setDraft((prev) => ({ ...prev, unit: event.target.value }))}
                          />
                        ) : (
                          result.unit || '—'
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {ok ? (
                          <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                            <Check className="h-3.5 w-3.5" />
                            {result.verification_status === 'verified' ? tr('Potvrđeno') : 'OK'}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            Proverite
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap justify-end gap-1">
                          {editing ? (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                disabled={busy}
                                onClick={() => {
                                  setError(null)
                                  updateMutation.mutate()
                                }}
                              >
                                {tr('Sačuvaj')}
                              </Button>
                              <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                                {tr('Otkaži')}
                              </Button>
                            </>
                          ) : (
                            <>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setEditingId(result.id)
                                  setDraft({
                                    value: result.value,
                                    unit: result.unit || '',
                                    original_parameter_name: result.original_parameter_name,
                                  })
                                }}
                              >
                                Izmeni
                              </Button>
                              <Button type="button" size="sm" variant="ghost" onClick={() => setSourcePreview(result)}>
                                {tr('Prikaži izvor')}
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {sourcePreview ? (
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium">Izvor: {sourcePreview.original_parameter_name}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {sourcePreview.source_page != null ? `Stranica ${sourcePreview.source_page}` : tr('Stranica nije poznata')}
                  {sourcePreview.extraction_confidence != null
                    ? ` · pouzdanost ${Number(sourcePreview.extraction_confidence).toFixed(2)}`
                    : ''}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-xs">{sourcePreview.raw_text || tr('Nema sačuvanog izvornog teksta.')}</p>
              </div>
              <div className="flex gap-1">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => void openSoilAnalysis(analysis)}
                >
                  <Eye className="h-4 w-4" />
                  PDF
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setSourcePreview(null)}>
                  Zatvori
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {adding ? (
          <div className="grid gap-3 rounded-lg border border-dashed border-border p-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Kod</Label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={addDraft.parameter_code}
                onChange={(event) => setAddDraft((prev) => ({ ...prev, parameter_code: event.target.value }))}
              >
                {PARAMETER_OPTIONS.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.label} ({item.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>{tr('Originalni naziv')}</Label>
              <Input
                value={addDraft.original_parameter_name}
                onChange={(event) => setAddDraft((prev) => ({ ...prev, original_parameter_name: event.target.value }))}
                placeholder={tr("npr. Reakcija zemljišta pH KCl")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Vrednost</Label>
              <Input
                value={addDraft.value}
                onChange={(event) => setAddDraft((prev) => ({ ...prev, value: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Jedinica</Label>
              <Input
                value={addDraft.unit}
                onChange={(event) => setAddDraft((prev) => ({ ...prev, unit: event.target.value }))}
              />
            </div>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button
                type="button"
                size="sm"
                disabled={busy || !addDraft.value.trim()}
                onClick={() => {
                  setError(null)
                  addMutation.mutate()
                }}
              >
                {tr('Sačuvaj parametar')}
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setAdding(false)}>
                {tr('Otkaži')}
              </Button>
            </div>
          </div>
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" />
            Dodaj parametar
          </Button>
        )}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={busy}
            onClick={() => {
              setError(null)
              verifyMutation.mutate()
            }}
          >
            <Check className="h-4 w-4" />
            {verifyMutation.isPending ? tr('Potvrđivanje…') : 'Potvrdi'}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy}
            onClick={() => {
              setError(null)
              skipMutation.mutate()
            }}
          >
            {tr('Preskoči')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function verificationLabel(status: SoilLabAnalysis['verification_status']) {
  switch (status) {
    case 'verified':
      return tr('Potvrđeno')
    case 'skipped':
      return tr('Preskočeno')
    case 'extracted':
      return 'Ekstrahovano'
    default:
      return 'Na pregledu'
  }
}
