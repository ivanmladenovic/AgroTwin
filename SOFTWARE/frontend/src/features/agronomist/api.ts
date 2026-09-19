import { apiRequest } from '@/shared/lib/api'
import type { AIStatus, ConversationDetail, ConversationSummary, DiseaseAnalysis } from '@/shared/api/types'

export function getAIStatus() {
  return apiRequest<AIStatus>('/ai/status')
}

export function listConversations() {
  return apiRequest<ConversationSummary[]>('/ai/conversations')
}

export function createConversation(title?: string) {
  return apiRequest<ConversationDetail>('/ai/conversations', {
    method: 'POST',
    body: JSON.stringify({ title: title || null }),
  })
}

export function getConversation(conversationId: string) {
  return apiRequest<ConversationDetail>(`/ai/conversations/${conversationId}`)
}

export function sendChatMessage(conversationId: string, content: string) {
  return apiRequest<ConversationDetail>(`/ai/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export function listDiseaseAnalyses(caseId: string) {
  return apiRequest<DiseaseAnalysis[]>(`/ai/disease-cases/${caseId}/analyses`)
}

export function requestDiseaseAnalysis(caseId: string, payload: { photo_id?: string | null; notes?: string | null }) {
  return apiRequest<DiseaseAnalysis>(`/ai/disease-cases/${caseId}/analyses`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}