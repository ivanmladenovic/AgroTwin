import { apiDownload, apiRequest, apiUpload, fetchObjectUrl } from '@/shared/lib/api'
import type { AgronomyQueryResult, KnowledgeCategory, KnowledgeDocument, KnowledgeHit } from '@/shared/api/types'

export function listKnowledgeDocuments() {
  return apiRequest<KnowledgeDocument[]>('/knowledge/documents')
}

export function uploadKnowledgeDocument(file: File, title: string, category: KnowledgeCategory, description?: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('title', title)
  form.append('category', category)
  if (description) form.append('description', description)
  return apiUpload<KnowledgeDocument>('/knowledge/documents', form)
}

export function deleteKnowledgeDocument(documentId: string) {
  return apiRequest<void>(`/knowledge/documents/${documentId}`, { method: 'DELETE' })
}

export function searchKnowledge(query: string) {
  return apiRequest<{ query: string; hits: KnowledgeHit[] }>(`/knowledge/search?q=${encodeURIComponent(query)}`)
}

export function queryAgronomy(question: string, debug = false) {
  return apiRequest<AgronomyQueryResult>('/ai/agronomy/query', {
    method: 'POST',
    body: JSON.stringify({ question, mode: 'retrieve', debug }),
  })
}

export function downloadKnowledgeDocument(document: Pick<KnowledgeDocument, 'id' | 'original_filename' | 'title'>) {
  return apiDownload(`/knowledge/documents/${document.id}/file`, document.original_filename || `${document.title}.pdf`)
}

export async function openKnowledgeDocument(document: Pick<KnowledgeDocument, 'id'>, page?: number | null) {
  const url = await fetchObjectUrl(`/knowledge/documents/${document.id}/file`)
  const parts = ['zoom=25']
  if (page && page > 0) parts.unshift(`page=${page}`)
  window.open(`${url}#${parts.join('&')}`, '_blank', 'noopener')
}
