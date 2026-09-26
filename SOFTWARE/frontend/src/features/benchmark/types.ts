export type BenchmarkMode = 'text' | 'image' | 'image_context' | 'full'

export type BenchmarkProviderId = 'gemini' | 'openai'

export type BenchmarkModelInfo = {
  id: string
  provider: string
  display_name: string
  model_id: string
  configured: boolean
}

export type BenchmarkTestCase = {
  id: string
  name: string
  mode: BenchmarkMode
  prompt: string
  context: unknown
  knowledge_evidence: unknown
}

export type BenchmarkConfig = {
  models: BenchmarkModelInfo[]
  defaults: {
    temperature: number
    max_output_tokens: number
    system_instruction: string
    max_image_bytes: number
    max_image_edge: number
    rate_limit_per_minute: number
  }
  pricing: Record<
    string,
    {
      input_usd_per_mtok: number
      output_usd_per_mtok: number
    }
  >
  modes: BenchmarkMode[]
  test_cases: BenchmarkTestCase[]
}

export type TokenUsage = {
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  reasoning_tokens: number | null
  cached_input_tokens: number | null
}

export type ProviderResult = {
  provider: string
  model: string
  status: string
  started_at: string
  ended_at: string
  latency_ms: number
  response_text: string | null
  error_code: string | null
  error_message: string | null
  usage: TokenUsage
  estimated_cost_usd: number | null
  generation_settings: Record<string, unknown>
  metadata_notes: string[]
  raw_metadata: Record<string, unknown>
}

export type BenchmarkRunResponse = {
  test_name: string
  mode: BenchmarkMode
  has_image: boolean
  prompt_preview: string
  system_instruction: string
  generation_settings: Record<string, unknown>
  equivalence_notes: string[]
  results: ProviderResult[]
  ran_at: string
}

export type BenchmarkRunPayload = {
  test_name: string
  mode: BenchmarkMode
  prompt: string
  providers: BenchmarkProviderId[]
  context_json?: string
  knowledge_evidence_json?: string
  system_instruction?: string
  temperature?: number
  max_output_tokens?: number
  photo_id?: string
  image?: File
}
