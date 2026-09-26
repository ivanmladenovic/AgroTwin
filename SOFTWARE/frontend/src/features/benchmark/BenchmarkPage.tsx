import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'

import { getBenchmarkConfig, runBenchmark } from '@/features/benchmark/api'
import type {
  BenchmarkMode,
  BenchmarkProviderId,
  BenchmarkRunResponse,
  ProviderResult,
} from '@/features/benchmark/types'
import { ApiError } from '@/shared/lib/api'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Textarea } from '@/shared/ui/textarea'

const MODE_OPTIONS: Array<{ value: BenchmarkMode; label: string }> = [
  { value: 'text', label: 'Text only' },
  { value: 'image', label: 'Image + text' },
  { value: 'image_context', label: 'Image + AgroTwin Context' },
  { value: 'full', label: 'Full test' },
]

const PROVIDER_LABELS: Record<string, string> = {
  gemini: 'Gemini 3.8 Flash',
  openai: 'GPT-5',
}

function pretty(value: unknown): string {
  if (value == null) return ''
  return JSON.stringify(value, null, 2)
}

function formatNa(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return 'N/A'
  if (digits > 0) return value.toFixed(digits)
  return String(value)
}

function formatCost(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return 'N/A'
  if (value < 0.0001) return `$${value.toFixed(8)}`
  return `$${value.toFixed(6)}`
}

async function copyText(text: string) {
  await navigator.clipboard.writeText(text)
}

export function BenchmarkPage() {
  const configQuery = useQuery({
    queryKey: ['benchmark-config'],
    queryFn: getBenchmarkConfig,
  })
  const config = configQuery.data

  const [testName, setTestName] = useState('Untitled test')
  const [mode, setMode] = useState<BenchmarkMode>('text')
  const [prompt, setPrompt] = useState('')
  const [contextJson, setContextJson] = useState('')
  const [evidenceJson, setEvidenceJson] = useState('')
  const [systemInstruction, setSystemInstruction] = useState('')
  const [photoId, setPhotoId] = useState('')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [useGemini, setUseGemini] = useState(true)
  const [useOpenAI, setUseOpenAI] = useState(true)
  const [result, setResult] = useState<BenchmarkRunResponse | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (config && !systemInstruction) {
      setSystemInstruction(config.defaults.system_instruction)
    }
  }, [config, systemInstruction])

  const mutation = useMutation({
    mutationFn: runBenchmark,
    onSuccess: (data) => {
      setResult(data)
      setFormError(null)
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : 'Pokretanje nije uspelo')
    },
  })

  function loadCase(id: string) {
    const item = config?.test_cases.find((entry) => entry.id === id)
    if (!item) return
    setTestName(item.name)
    setMode(item.mode)
    setPrompt(item.prompt)
    setContextJson(pretty(item.context))
    setEvidenceJson(pretty(item.knowledge_evidence))
  }

  function onImageChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null
    setImageFile(file)
    if (file && mode === 'text') {
      setMode('image')
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    const providers: BenchmarkProviderId[] = []
    if (useGemini) providers.push('gemini')
    if (useOpenAI) providers.push('openai')
    if (!providers.length) {
      setFormError('Izaberite bar jedan model')
      return
    }
    if (!prompt.trim()) {
      setFormError('Prompt je obavezan')
      return
    }
    mutation.mutate({
      test_name: testName,
      mode,
      prompt,
      providers,
      context_json: contextJson,
      knowledge_evidence_json: evidenceJson,
      system_instruction: systemInstruction,
      temperature: config?.defaults.temperature,
      max_output_tokens: config?.defaults.max_output_tokens,
      photo_id: photoId.trim() || undefined,
      image: imageFile ?? undefined,
    })
  }

  function clearResults() {
    setResult(null)
  }

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Razvoj</p>
        <h1 className="mt-1 text-xl font-semibold sm:text-2xl">AI Model Benchmark</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
          Interni alat za upoređivanje Gemini 3.8 Flash i GPT-5 na istom ulazu. Nema automatskog
          pobednika — rezultate ocenjujete ručno.
        </p>
      </div>

      {configQuery.isError ? (
        <Card>
          <CardContent className="pt-6 text-sm text-destructive">
            {configQuery.error instanceof ApiError
              ? configQuery.error.message
              : 'Učitavanje konfiguracije nije uspelo'}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Unapred definisani testovi</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {(config?.test_cases ?? []).map((item) => (
            <Button key={item.id} type="button" variant="outline" size="sm" onClick={() => loadCase(item.id)}>
              {item.name}
            </Button>
          ))}
        </CardContent>
      </Card>

      <form onSubmit={onSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Test input</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="bench-name">Test name</Label>
              <Input id="bench-name" value={testName} onChange={(e) => setTestName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bench-prompt">Prompt</Label>
              <Textarea
                id="bench-prompt"
                className="min-h-32"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                required
              />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="bench-image">Image</Label>
                <Input id="bench-image" type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" onChange={onImageChange} />
                {imageFile ? (
                  <p className="text-xs text-muted-foreground">
                    {imageFile.name} ({Math.round(imageFile.size / 1024)} KB)
                  </p>
                ) : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="bench-photo">Optional AgroTwin photo ID</Label>
                <Input
                  id="bench-photo"
                  value={photoId}
                  onChange={(e) => setPhotoId(e.target.value)}
                  placeholder="UUID postojeće fotografije"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="bench-context">Context (JSON)</Label>
              <Textarea
                id="bench-context"
                className="min-h-40 font-mono text-xs"
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
                placeholder='{"parcel":{"name":"Test Parcel","crop":"Hazelnut"}}'
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bench-evidence">Knowledge evidence (JSON)</Label>
              <Textarea
                id="bench-evidence"
                className="min-h-40 font-mono text-xs"
                value={evidenceJson}
                onChange={(e) => setEvidenceJson(e.target.value)}
                placeholder='[{"source":"...","content":"..."}]'
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="bench-system">System instruction</Label>
              <Textarea
                id="bench-system"
                className="min-h-32 font-mono text-xs"
                value={systemInstruction}
                onChange={(e) => setSystemInstruction(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Mode</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {MODE_OPTIONS.map((item) => (
                <label key={item.value} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="bench-mode"
                    value={item.value}
                    checked={mode === item.value}
                    onChange={() => setMode(item.value)}
                  />
                  {item.label}
                </label>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Models</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={useGemini} onChange={(e) => setUseGemini(e.target.checked)} />
                Gemini 3.8 Flash
                {config ? (
                  <span className="text-xs text-muted-foreground">
                    ({config.models.find((m) => m.id === 'gemini')?.configured ? 'key set' : 'key missing'})
                  </span>
                ) : null}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={useOpenAI} onChange={(e) => setUseOpenAI(e.target.checked)} />
                GPT-5
                {config ? (
                  <span className="text-xs text-muted-foreground">
                    ({config.models.find((m) => m.id === 'openai')?.configured ? 'key set' : 'key missing'})
                  </span>
                ) : null}
              </label>
              {config ? (
                <p className="text-xs text-muted-foreground">
                  Defaults: temperature {config.defaults.temperature}, max output{' '}
                  {config.defaults.max_output_tokens} tokens. Pricing is server-configured.
                </p>
              ) : null}
            </CardContent>
          </Card>
        </div>

        {formError ? <p className="text-sm text-destructive">{formError}</p> : null}

        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Running…' : 'Run comparison'}
          </Button>
          <Button type="button" variant="outline" onClick={clearResults} disabled={!result}>
            Clear results
          </Button>
        </div>
      </form>

      {result ? (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Results</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {result.test_name} · mode={result.mode} · {result.has_image ? 'image + text' : 'text only'} ·{' '}
              {new Date(result.ran_at).toLocaleString()}
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {result.results.map((item) => (
              <ResultCard key={item.provider} result={item} />
            ))}
          </div>
          {result.equivalence_notes.length ? (
            <Card>
              <CardHeader>
                <CardTitle>Equivalence notes</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {result.equivalence_notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}

function ResultCard({ result }: { result: ProviderResult }) {
  const [copied, setCopied] = useState<string | null>(null)
  const title = PROVIDER_LABELS[result.provider] ?? result.provider
  const ok = result.status === 'success'

  async function handleCopy(kind: 'response' | 'json') {
    const text =
      kind === 'response'
        ? result.response_text || result.error_message || ''
        : JSON.stringify(result, null, 2)
    await copyText(text)
    setCopied(kind)
    window.setTimeout(() => setCopied(null), 1500)
  }

  return (
    <Card className={ok ? undefined : 'border-destructive/40'}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-baseline justify-between gap-2">
          <span>{title}</span>
          <span className="text-xs font-normal text-muted-foreground">{result.model}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
          <dt className="text-muted-foreground">Status</dt>
          <dd className={ok ? 'text-foreground' : 'text-destructive'}>{result.status}</dd>
          <dt className="text-muted-foreground">Latency</dt>
          <dd>{result.latency_ms} ms</dd>
          <dt className="text-muted-foreground">Input tokens</dt>
          <dd>{formatNa(result.usage.input_tokens)}</dd>
          <dt className="text-muted-foreground">Output tokens</dt>
          <dd>{formatNa(result.usage.output_tokens)}</dd>
          <dt className="text-muted-foreground">Total tokens</dt>
          <dd>{formatNa(result.usage.total_tokens)}</dd>
          <dt className="text-muted-foreground">Reasoning tokens</dt>
          <dd>{formatNa(result.usage.reasoning_tokens)}</dd>
          <dt className="text-muted-foreground">Estimated cost</dt>
          <dd>{formatCost(result.estimated_cost_usd)}</dd>
        </dl>

        {ok ? (
          <div className="rounded-lg border border-border bg-muted/30 p-3 whitespace-pre-wrap break-words">
            {result.response_text || '—'}
          </div>
        ) : (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-destructive">
            <p className="font-medium">{result.error_code || 'error'}</p>
            <p className="mt-1">{result.error_message || 'Nepoznata greška'}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => void handleCopy('response')}>
            {copied === 'response' ? 'Copied' : 'Copy response'}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void handleCopy('json')}>
            {copied === 'json' ? 'Copied' : 'Copy JSON'}
          </Button>
        </div>

        <details className="rounded-lg border border-border p-3">
          <summary className="cursor-pointer text-xs font-medium">Raw response metadata</summary>
          <pre className="mt-2 overflow-x-auto text-xs text-muted-foreground">
            {JSON.stringify(
              {
                generation_settings: result.generation_settings,
                metadata_notes: result.metadata_notes,
                raw_metadata: result.raw_metadata,
                started_at: result.started_at,
                ended_at: result.ended_at,
              },
              null,
              2,
            )}
          </pre>
        </details>
      </CardContent>
    </Card>
  )
}
