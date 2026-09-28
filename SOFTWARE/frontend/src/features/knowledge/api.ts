import { apiDownload, apiRequest, apiUpload, ApiError, fetchObjectUrl } from '@/shared/lib/api'
import { getAccessToken } from '@/shared/lib/auth'
import type { AgronomyQueryResult, KnowledgeCategory, KnowledgeDocument, KnowledgeHit } from '@/shared/api/types'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1'

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

export function knowledgeDocumentFilePath(documentId: string) {
  return `/knowledge/documents/${documentId}/file`
}

export function knowledgePdfViewerUrl(objectUrl: string, page?: number | null) {
  const parts: string[] = []
  if (page && page > 0) parts.push(`page=${page}`)
  parts.push('zoom=page-width')
  return `${objectUrl}#${parts.join('&')}`
}

/** Load PDF as a blob URL (auth required). Caller must revoke when done. */
export function fetchKnowledgeDocumentUrl(documentId: string) {
  return fetchObjectUrl(knowledgeDocumentFilePath(documentId))
}

/** Load raw PDF bytes for in-app pdf.js viewing. */
export async function fetchKnowledgeDocumentBytes(documentId: string): Promise<ArrayBuffer> {
  const token = getAccessToken()
  let response: Response
  try {
    response = await fetch(`${API_URL}${knowledgeDocumentFilePath(documentId)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch {
    throw new ApiError('Veza sa serverom nije uspela. Proverite mrežu i pokušajte ponovo.', 0)
  }
  if (!response.ok) {
    let detail = 'PDF nije učitan'
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, response.status)
  }
  return response.arrayBuffer()
}

/**
 * Open PDF in a new tab at an optional page.
 * Opens the window synchronously first so mobile browsers do not block the popup
 * after the authenticated fetch completes.
 * Returns false when the popup was blocked (caller should show an in-app viewer).
 */
export async function openKnowledgeDocument(document: Pick<KnowledgeDocument, 'id'>, page?: number | null) {
  const popup = window.open('about:blank', '_blank')
  try {
    const objectUrl = await fetchKnowledgeDocumentUrl(document.id)
    const target = knowledgePdfViewerUrl(objectUrl, page)
    if (popup && !popup.closed) {
      popup.location.replace(target)
      return true
    }
    return false
  } catch (error) {
    popup?.close()
    throw error
  }
}
