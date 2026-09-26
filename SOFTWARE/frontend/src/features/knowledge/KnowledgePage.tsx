import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, Plus, Search, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  listKnowledgeDocuments,
  openKnowledgeDocument,
  queryAgronomy,
  searchKnowledge,
  uploadKnowledgeDocument,
} from '@/features/knowledge/api'
import { cleanKnowledgeExcerpt, highlightParts } from '@/features/knowledge/excerpt'
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

export function KnowledgePage() {
  const docsQuery = useQuery({ queryKey: ['knowledge-docs'], queryFn: listKnowledgeDocuments })
  const [adding, setAdding] = useState(false)
  const [query, setQuery] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [agronomyTerm, setAgronomyTerm] = useState('')
  const searchQuery = useQuery({
    queryKey: ['knowledge-search', searchTerm],
    queryFn: () => searchKnowledge(searchTerm),
    enabled: searchTerm.length > 0,
  })
  const agronomyQuery = useQuery({
    queryKey: ['agronomy-query', agronomyTerm],
    queryFn: () => queryAgronomy(agronomyTerm),
    enabled: agronomyTerm.length > 0,
  })

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
              <ManualRow key={doc.id} document={doc} />
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
            <div className="flex gap-2">
              <Button type="submit" variant="outline" disabled={!query.trim() || searchQuery.isFetching}>
                <Search className="h-4 w-4" />
                {searchQuery.isFetching ? 'Pretraga…' : 'Pretraži'}
              </Button>
              <Button
                type="button"
                disabled={!query.trim() || agronomyQuery.isFetching}
                onClick={() => {
                  const next = query.trim()
                  if (!next) return
                  setAgronomyTerm(next)
                }}
              >
                Agronomska pretraga
              </Button>
            </div>
          </form>

          {searchQuery.isError ? (
            <p className="text-sm text-danger">
              {searchQuery.error instanceof Error ? searchQuery.error.message : 'Pretraga nije uspela'}
            </p>
          ) : null}

          {searchQuery.data && searchTerm ? (
            <div className="space-y-3">
              {(searchQuery.data.hits ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">Nema odlomaka za „{searchTerm}“.</p>
              ) : (
                searchQuery.data.hits.map((hit) => (
                  <SearchHitCard
                    key={hit.chunk_id}
                    hit={hit}
                    query={searchTerm}
                  />
                ))
              )}
            </div>
          ) : null}

          {agronomyQuery.isFetching ? <p className="text-sm text-muted-foreground">Agronomska pretraga…</p> : null}
          {agronomyQuery.isError ? (
            <p className="text-sm text-danger">
              {agronomyQuery.error instanceof Error ? agronomyQuery.error.message : 'Agronomska pretraga nije uspela'}
            </p>
          ) : null}
          {agronomyQuery.data ? (
            <div className="space-y-3 rounded-xl border border-border p-4">
              <p className="text-sm font-medium">
                {agronomyQuery.data.out_of_scope
                  ? 'Pitanje je van obima priručnika'
                  : agronomyQuery.data.sufficient_evidence
                    ? 'Odgovor iz priručnika'
                    : 'Nedovoljno dokaza u priručnicima'}
              </p>
              {cleanKnowledgeExcerpt(agronomyQuery.data.answer, agronomyTerm).map((paragraph) => (
                <p key={paragraph} className="text-sm leading-6 text-foreground">
                  <HighlightedText text={paragraph} query={agronomyTerm} />
                </p>
              ))}
              {agronomyQuery.data.citations.length > 0 ? (
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {agronomyQuery.data.citations.map((citation) => (
                    <li key={citation}>{citation}</li>
                  ))}
                </ul>
              ) : null}
              {(agronomyQuery.data.evidence?.sources ?? []).map((source, index) => (
                <SearchHitCard
                  key={`${source.document_id}-${index}`}
                  hit={{
                    chunk_id: `${source.document_id}-${index}`,
                    document_id: source.document_id,
                    document_title: source.document_title,
                    category: 'other',
                    page_number: source.pages[0] ?? null,
                    section_title: source.section,
                    content: source.content,
                    score: 0,
                  }}
                  query={agronomyTerm}
                />
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function ManualRow({
  document,
}: {
  document: KnowledgeDocument
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
          onClick={() => void openKnowledgeDocument(document)}
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
  query,
}: {
  hit: KnowledgeHit
  query: string
}) {
  const paragraphs = cleanKnowledgeExcerpt(hit.content, query)
  return (
    <article className="space-y-2 rounded-xl border border-border bg-background p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">{hit.document_title}</p>
          <p className="text-xs text-muted-foreground">
            {hit.page_number ? `Strana ${hit.page_number}` : 'Strana nije navedena'}
            {hit.section_title ? ` · ${hit.section_title}` : ''}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => void openKnowledgeDocument({ id: hit.document_id }, hit.page_number)}
        >
          <Eye className="h-4 w-4" />
          Otvori
        </Button>
      </div>
      {paragraphs.length === 0 ? (
        <p className="text-sm text-muted-foreground">Odlomak nije mogao da se prikaže čitljivo. Otvorite priručnik.</p>
      ) : (
        paragraphs.map((paragraph) => (
          <p key={paragraph} className="text-sm leading-6 text-foreground">
            <HighlightedText text={paragraph} query={query} />
          </p>
        ))
      )}
    </article>
  )
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  return (
    <>
      {highlightParts(text, query).map((part, index) =>
        part.match ? (
          <mark key={`${part.text}-${index}`} className="rounded bg-accent/20 text-foreground">
            {part.text}
          </mark>
        ) : (
          <span key={`${part.text}-${index}`}>{part.text}</span>
        ),
      )}
    </>
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
                <Label>PDF datoteka</Label>
                <Input type="file" accept="application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Beleške</Label>
              <Textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
            </div>
            {uploadMutation.isError ? (
              <p className="text-sm text-danger">
                {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Otpremanje nije uspelo'}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={uploadMutation.isPending || !file}>
                {uploadMutation.isPending ? 'Indeksiranje…' : 'Otpremi i indeksiraj'}
              </Button>
              <Button type="button" variant="outline" disabled={uploadMutation.isPending} onClick={onClose}>
                Otkaži
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
