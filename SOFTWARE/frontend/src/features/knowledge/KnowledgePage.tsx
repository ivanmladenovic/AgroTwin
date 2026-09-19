import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { deleteKnowledgeDocument, listKnowledgeDocuments, queryAgronomy, searchKnowledge, uploadKnowledgeDocument } from '@/features/knowledge/api'
import type { KnowledgeCategory } from '@/shared/api/types'
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
  const queryClient = useQueryClient()
  const docsQuery = useQuery({ queryKey: ['knowledge-docs'], queryFn: listKnowledgeDocuments })
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState<KnowledgeCategory>('other')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [query, setQuery] = useState('Koja je uloga kalijuma kod leske?')
  const searchQuery = useQuery({
    queryKey: ['knowledge-search', query],
    queryFn: () => searchKnowledge(query),
    enabled: false,
  })
  const agronomyQuery = useQuery({
    queryKey: ['agronomy-query', query],
    queryFn: () => queryAgronomy(query, true),
    enabled: false,
  })

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error('Izaberite PDF')
      return uploadKnowledgeDocument(file, title || file.name, category, description || undefined)
    },
    onSuccess: async () => {
      setTitle('')
      setDescription('')
      setFile(null)
      await queryClient.invalidateQueries({ queryKey: ['knowledge-docs'] })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteKnowledgeDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['knowledge-docs'] })
    },
  })

  function onUpload(event: FormEvent) {
    event.preventDefault()
    uploadMutation.mutate()
  }

  return (
    <div className="w-full space-y-6">
      <div>
        <p className="kicker">Baza znanja</p>
          <h1 className="mt-1 text-xl font-semibold sm:text-2xl">Priručnici voćnjaka</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Otpremite PDF-ove. AgroTwin izvlači tekst, seče ga na odlomke i čuva ugrađivanja za agronoma. Ovo je
          referentni materijal, a ne dijagnoza.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Otpremi PDF</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-3 md:grid-cols-2" onSubmit={onUpload}>
            <div className="space-y-1.5 md:col-span-2">
              <Label>Naslov</Label>
              <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Priručnik za lesnik" />
            </div>
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
            <div className="space-y-1.5 md:col-span-2">
              <Label>Beleške</Label>
              <Textarea rows={2} value={description} onChange={(event) => setDescription(event.target.value)} />
            </div>
            {uploadMutation.isError ? (
              <p className="text-sm text-danger md:col-span-2">
                {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Otpremanje nije uspelo'}
              </p>
            ) : null}
            <div>
              <Button type="submit" disabled={uploadMutation.isPending || !file}>
                {uploadMutation.isPending ? 'Indeksiranje…' : 'Otpremi i indeksiraj'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Indeksirani dokumenti</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {(docsQuery.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">Još nema priručnika.</p>
          ) : (
            (docsQuery.data ?? []).map((doc) => (
              <div key={doc.id} className="flex items-start justify-between gap-4 border-b border-border pb-3 last:border-0">
                <div>
                  <p className="font-medium">{doc.title}</p>
                  <p className="text-sm text-muted-foreground">
                    {categoryLabel(doc.category)} · {documentStatusLabels[doc.status] ?? doc.status}
                    {doc.source_kind === 'agriser_manual' ? ' · Agriser' : ''}
                    {doc.page_count ? ` · ${doc.page_count} str.` : ''} · {doc.chunk_count} odlomaka
                    {doc.image_count ? ` · ${doc.image_count} slika` : ''}
                  </p>
                  {doc.processed_at ? (
                    <p className="text-xs text-muted-foreground">
                      Obrađeno: {new Date(doc.processed_at).toLocaleString('sr-Latn-RS')}
                    </p>
                  ) : null}
                  {doc.error_message ? <p className="text-xs text-danger">{doc.error_message}</p> : null}
                </div>
                <Button variant="outline" size="sm" onClick={() => deleteMutation.mutate(doc.id)}>
                  Ukloni
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provera pretrage</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input value={query} onChange={(event) => setQuery(event.target.value)} />
            <Button type="button" variant="outline" onClick={() => void searchQuery.refetch()}>
              Pretraži
            </Button>
            <Button type="button" onClick={() => void agronomyQuery.refetch()}>
              Agronomska pretraga
            </Button>
          </div>
          {(searchQuery.data?.hits ?? []).map((hit) => (
            <div key={hit.chunk_id} className="border border-border p-3 text-sm">
              <p className="font-medium">
                {hit.document_title}
                {hit.page_number ? ` · str. ${hit.page_number}` : ''}
              </p>
              <p className="mt-1 text-muted-foreground">{hit.content}</p>
            </div>
          ))}
          {agronomyQuery.data ? (
            <div className="space-y-2 border border-border p-3 text-sm">
              <p className="font-medium">{agronomyQuery.data.sufficient_evidence ? 'Dokazi pronađeni' : 'Nedovoljno dokaza'}</p>
              {agronomyQuery.data.debug ? (
                <p className="text-xs text-muted-foreground">
                  {agronomyQuery.data.debug.detected_domain || 'n/a'} → {agronomyQuery.data.debug.detected_topic || 'n/a'} ·
                  odlomaka {agronomyQuery.data.debug.selected_chunks}/{agronomyQuery.data.debug.retrieved_chunks} ·
                  pouzdanost {agronomyQuery.data.debug.confidence}
                </p>
              ) : null}
              <pre className="whitespace-pre-wrap text-xs text-muted-foreground">{agronomyQuery.data.answer}</pre>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
