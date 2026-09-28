import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, Plus, Search, X } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  listKnowledgeDocuments,
  searchKnowledge,
  uploadKnowledgeDocument,
} from '@/features/knowledge/api'
import { KnowledgePdfScrollViewer } from '@/features/knowledge/KnowledgePdfScrollViewer'
import type { KnowledgeCategory, KnowledgeDocument, KnowledgeHit } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Input } from '@/shared/ui/input'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

const categories: Array<{ value: KnowledgeCategory; label: string }> = [
  { value: 'plant_protection', label: 'Zaštita' },
  { value: 'nutrition_guide', label: 'Prihrana' },
  { value: 'other', label: 'Uopšteno' },
]

function categoryLabel(value: string) {
  if (value === 'plant_protection' || value === 'disease_guide' || value === 'pest_guide') return 'Zaštita'
  if (value === 'nutrition_guide') return 'Prihrana'
  return 'Uopšteno'
}

const documentStatusLabels: Record<string, string> = {
  pending: 'na čekanju',
  processing: 'obrada',
  ready: 'indeksirano',
  failed: 'neuspelo',
}

type PdfViewerTarget = {
  documentId: string
  title: string
  page?: number | null
  filename?: string | null
}

export function KnowledgePage() {
  const docsQuery = useQuery({ queryKey: ['knowledge-docs'], queryFn: listKnowledgeDocuments })
  const [searchParams, setSearchParams] = useSearchParams()
  const [adding, setAdding] = useState(false)
  const [viewer, setViewer] = useState<PdfViewerTarget | null>(null)
  const [query, setQuery] = useState(() => searchParams.get('q') || '')
  const [searchTerm, setSearchTerm] = useState(() => searchParams.get('q') || '')
  const searchQuery = useQuery({
    queryKey: ['knowledge-search', searchTerm],
    queryFn: () => searchKnowledge(searchTerm),
    enabled: searchTerm.length > 0,
  })

  useEffect(() => {
    const next = new URLSearchParams()
    if (searchTerm) next.set('q', searchTerm)
    if (next.toString() === searchParams.toString()) return
    setSearchParams(next, { replace: true })
  }, [searchParams, searchTerm, setSearchParams])

  function runSearch(event: FormEvent) {
    event.preventDefault()
    const next = query.trim()
    if (!next) return
    setSearchTerm(next)
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="kicker">Baza znanja</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Priručnici voćnjaka</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Pregledajte i preuzmite priručnike, ili pretražite odlomke. Ovo je referentni materijal, a ne dijagnoza.
          </p>
        </div>
        <Button type="button" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" />
          Dodaj priručnik
        </Button>
      </div>

      {adding ? <UploadManualForm onClose={() => setAdding(false)} /> : null}
      {viewer ? <KnowledgePdfViewer target={viewer} onClose={() => setViewer(null)} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Priručnici</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {docsQuery.isLoading ? (
            <p className="text-sm text-muted-foreground">Učitavanje priručnika…</p>
          ) : (docsQuery.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Još nema priručnika.</p>
          ) : (
            (docsQuery.data ?? []).map((doc) => (
              <ManualRow key={doc.id} document={doc} onOpen={setViewer} />
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pretraga priručnika</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form className="flex flex-col gap-2 sm:flex-row" onSubmit={runSearch}>
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="npr. magnezijum, rezidba, suša"
              aria-label="Pojam za pretragu"
            />
            <Button type="submit" variant="outline" disabled={!query.trim() || searchQuery.isFetching}>
              <Search className="h-4 w-4" />
              {searchQuery.isFetching ? 'Pretraga…' : 'Pretraži'}
            </Button>
          </form>

          {searchQuery.isError ? (
            <p className="text-sm text-danger">
              {searchQuery.error instanceof Error ? searchQuery.error.message : 'Pretraga nije uspela'}
            </p>
          ) : null}

          {searchQuery.data && searchTerm ? (
            <div className="space-y-3">
              {(searchQuery.data.hits ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Nema pogodaka za „{searchTerm}“.</p>
              ) : (
                searchQuery.data.hits.map((hit) => (
                  <SearchHitCard key={hit.chunk_id} hit={hit} onOpen={setViewer} />
                ))
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function ManualRow({
  document,
  onOpen,
}: {
  document: KnowledgeDocument
  onOpen: (target: PdfViewerTarget) => void
}) {
  const queryClient = useQueryClient()
  const deleteMutation = useMutation({
    mutationFn: () => deleteKnowledgeDocument(document.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['knowledge-docs'] })
    },
  })

  return (
    <div className="flex flex-col gap-3 border-b border-border pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <p className="font-medium">{document.title}</p>
        <p className="text-sm text-muted-foreground">
          {categoryLabel(document.category)} · {documentStatusLabels[document.status] ?? document.status}
          {document.source_kind === 'agriser_manual' ? ' · Agriser' : ''}
          {document.page_count ? ` · ${document.page_count} str.` : ''}
        </p>
        {document.error_message ? <p className="text-xs text-danger">{document.error_message}</p> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() =>
            onOpen({
              documentId: document.id,
              title: document.title,
              filename: document.original_filename,
            })
          }
        >
          <Eye className="h-4 w-4" />
          Otvori
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => void downloadKnowledgeDocument(document)}>
          <Download className="h-4 w-4" />
          Preuzmi
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm('Ukloniti ovaj priručnik iz baze znanja?')) {
              deleteMutation.mutate()
            }
          }}
        >
          Ukloni
        </Button>
      </div>
    </div>
  )
}

function SearchHitCard({
  hit,
  onOpen,
}: {
  hit: KnowledgeHit
  onOpen: (target: PdfViewerTarget) => void
}) {
  const location = [
    hit.page_number ? `Strana ${hit.page_number}` : null,
    hit.section_title?.trim() || null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <article className="rounded-xl border border-border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{hit.document_title}</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {location || 'Lokacija u priručniku nije navedena'}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="shrink-0"
          onClick={() =>
            onOpen({
              documentId: hit.document_id,
              title: hit.document_title,
              page: hit.page_number,
            })
          }
        >
          <Eye className="h-4 w-4" />
          Otvori
        </Button>
      </div>
    </article>
  )
}

function KnowledgePdfViewer({
  target,
  onClose,
}: {
  target: PdfViewerTarget
  onClose: () => void
}) {
  const pageLabel = target.page && target.page > 0 ? `Strana ${target.page}` : null

  async function handleDownload() {
    await downloadKnowledgeDocument({
      id: target.documentId,
      title: target.title,
      original_filename: target.filename || undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-[2100] flex flex-col bg-background">
      <header className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{target.title}</p>
          {pageLabel ? (
            <p className="mt-0.5 text-xs text-muted-foreground">
              Otvoreno na {pageLabel.toLowerCase()} · skrolujte za ostale strane
            </p>
          ) : (
            <p className="mt-0.5 text-xs text-muted-foreground">Skrolujte kroz PDF</p>
          )}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => void handleDownload()}>
            <Download className="h-4 w-4" />
            Preuzmi
          </Button>
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg hover:bg-muted"
            aria-label="Zatvori"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1">
        <KnowledgePdfScrollViewer
          documentId={target.documentId}
          title={target.title}
          page={target.page}
          className="h-full overflow-auto bg-muted/40"
        />
      </div>
    </div>
  )
}

function UploadManualForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<KnowledgeCategory>('other')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Izaberite PDF')
      return uploadKnowledgeDocument(file, title || file.name, category, description || undefined)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['knowledge-docs'] })
      onClose()
    },
  })

  function onUpload(event: FormEvent) {
    event.preventDefault()
    uploadMutation.mutate()
  }

  return (
    <div className="fixed inset-0 z-[2000] flex items-end justify-center bg-foreground/40 p-0 sm:items-center sm:p-4">
      <Card className="w-full max-w-lg rounded-t-2xl sm:rounded-2xl">
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Novi priručnik</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">Otpremite PDF. AgroTwin izvlači tekst za pretragu i agronoma.</p>
          </div>
          <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted" aria-label="Zatvori" onClick={onClose}>
            <X className="h-4 w-4" />
          </button>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3" onSubmit={onUpload}>
            <div className="space-y-1.5">
              <Label>Naslov</Label>
              <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Priručnik za lesnik" />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Kategorija</Label>
                <Select value={category} onChange={(event) => setCategory(event.target.value as KnowledgeCategory)}>
                  {categories.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>PDF fajl</Label>
                <Input
                  type="file"
                  accept="application/pdf"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Opis (opciono)</Label>
              <Textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
            </div>
            {uploadMutation.error ? (
              <p className="text-sm text-danger">
                {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Otpremanje nije uspelo'}
              </p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Otkaži
              </Button>
              <Button type="submit" disabled={!file || uploadMutation.isPending}>
                {uploadMutation.isPending ? 'Otpremanje…' : 'Sačuvaj'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
