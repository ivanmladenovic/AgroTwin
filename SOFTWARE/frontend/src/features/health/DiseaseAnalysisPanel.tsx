import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { listDiseaseAnalyses, requestDiseaseAnalysis } from '@/features/agronomist/api'
import type { PhotoRecord } from '@/shared/api/types'
import { Button } from '@/shared/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/ui/card'
import { Label } from '@/shared/ui/label'
import { Select } from '@/shared/ui/select'
import { Textarea } from '@/shared/ui/textarea'

export function DiseaseAnalysisPanel({ caseId, photos }: { caseId: string; photos: PhotoRecord[] }) {
  const queryClient = useQueryClient()
  const [photoId, setPhotoId] = useState(photos[0]?.id ?? '')
  const [notes, setNotes] = useState('')
  const listQuery = useQuery({
    queryKey: ['disease-analyses', caseId],
    queryFn: () => listDiseaseAnalyses(caseId),
  })
  const mutation = useMutation({
    mutationFn: () =>
      requestDiseaseAnalysis(caseId, {
        photo_id: photoId || null,
        notes: notes || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['disease-analyses', caseId] })
    },
  })
  const latest = listQuery.data?.[0]

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI čitanje</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Pomoćnik može da komentariše fotografiju na osnovu istorije stabla i priručnika. Neće potvrditi dijagnozu niti
          izmisliti nazive proizvoda.
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label>Fotografija</Label>
            <Select value={photoId} onChange={(event) => setPhotoId(event.target.value)}>
              <option value="">Koristi poslednju fotografiju stabla</option>
              {photos.map((photo) => (
                <option key={photo.id} value={photo.id}>
                  {photo.caption || photo.original_filename}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label>Dodatne beleške za pomoćnika</Label>
            <Textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
          </div>
        </div>
        <Button type="button" size="sm" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? 'Čitanje fotografije…' : 'Zatraži AI analizu'}
        </Button>
        {mutation.isError ? (
          <p className="text-sm text-danger">
            {mutation.error instanceof Error ? mutation.error.message : 'Analiza nije uspela'}
          </p>
        ) : null}
        {latest ? (
          <div className="space-y-3 border border-border bg-muted/30 p-4 text-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Mogući problem — nije potvrđeno</p>
            <p className="text-lg font-medium">{latest.likely_issue}</p>
            <p className="text-muted-foreground">Pouzdanost {Math.round(latest.confidence * 100)}%</p>
            <section>
              <p className="font-medium">Uočene činjenice</p>
              <p className="mt-1 text-muted-foreground">{latest.observed_facts}</p>
            </section>
            {latest.observed_symptoms.length > 0 ? (
              <section>
                <p className="font-medium">Zabeleženi simptomi</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {latest.observed_symptoms.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            ) : null}
            <section>
              <p className="font-medium">Neizvesnost</p>
              <p className="mt-1 text-muted-foreground">{latest.uncertainty_notes}</p>
            </section>
            <section>
              <p className="font-medium">Druge mogućnosti</p>
              <p className="mt-1 text-muted-foreground">{latest.possible_alternatives.join(' · ') || '—'}</p>
            </section>
            <section>
              <p className="font-medium">Preporučeni pregled</p>
              <p className="mt-1">{latest.recommended_inspection}</p>
            </section>
            <section>
              <p className="font-medium">Sledeći korak</p>
              <p className="mt-1">{latest.recommended_next_step}</p>
            </section>
            {latest.supporting_sources.length > 0 ? (
              <section>
                <p className="font-medium">Izvori</p>
                <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                  {latest.supporting_sources.map((source, index) => (
                    <li key={`${source.document_title}-${index}`}>
                      {source.document_title}
                      {source.page_number ? ` · p. ${source.page_number}` : ''}
                    </li>
                  ))}
                </ul>
              </section>
            ) : (
              <p className="text-muted-foreground">Nijedan odlomak iz priručnika nije bio dovoljno jak za citiranje.</p>
            )}
            <p className="text-xs text-muted-foreground">{latest.disclaimer}</p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}