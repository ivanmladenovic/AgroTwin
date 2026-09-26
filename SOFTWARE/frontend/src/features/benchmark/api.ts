import { apiRequest, apiUpload } from '@/shared/lib/api'
import type {
  BenchmarkConfig,
  BenchmarkRunResponse,
  BenchmarkRunPayload,
} from '@/features/benchmark/types'

export function getBenchmarkConfig() {
  return apiRequest<BenchmarkConfig>('/benchmark/config')
}

export function runBenchmark(payload: BenchmarkRunPayload) {
  const form = new FormData()
  form.append('test_name', payload.test_name)
  form.append('mode', payload.mode)
  form.append('prompt', payload.prompt)
  form.append('providers', payload.providers.join(','))
  if (payload.context_json?.trim()) {
    form.append('context_json', payload.context_json)
  }
  if (payload.knowledge_evidence_json?.trim()) {
    form.append('knowledge_evidence_json', payload.knowledge_evidence_json)
  }
  if (payload.system_instruction?.trim()) {
    form.append('system_instruction', payload.system_instruction)
  }
  if (payload.temperature != null) {
    form.append('temperature', String(payload.temperature))
  }
  if (payload.max_output_tokens != null) {
    form.append('max_output_tokens', String(payload.max_output_tokens))
  }
  if (payload.photo_id) {
    form.append('photo_id', payload.photo_id)
  }
  if (payload.image) {
    form.append('image', payload.image)
  }
  return apiUpload<BenchmarkRunResponse>('/benchmark/run', form)
}
