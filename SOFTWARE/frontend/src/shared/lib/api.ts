import { expireAccessToken, getAccessToken } from '@/shared/lib/auth'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '/api/v1'

export class ApiError extends Error {
  status: number
  code?: string

  constructor(message: string, status: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type RequestOptions = RequestInit & {
  skipAuth?: boolean
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { detail?: string; code?: string }
    return new ApiError(body.detail ?? 'Zahtev nije uspeo', response.status, body.code)
  } catch {
    return new ApiError(response.statusText || 'Zahtev nije uspeo', response.status)
  }
}

function handleUnauthorized(sentToken: string | null): void {
  if (expireAccessToken(sentToken) && window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth, headers, ...rest } = options
  const token = skipAuth ? null : getAccessToken()
  const hasJsonBody = typeof rest.body === 'string'

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      ...(hasJsonBody ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })

  if (response.status === 401 && !skipAuth) {
    handleUnauthorized(token)
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const token = getAccessToken()
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  if (response.status === 401) {
    handleUnauthorized(token)
  }
  if (!response.ok) {
    throw await parseError(response)
  }
  return (await response.json()) as T
}

export async function fetchObjectUrl(path: string): Promise<string> {
  const token = getAccessToken()
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (response.status === 401) {
    handleUnauthorized(token)
  }
  if (!response.ok) {
    throw await parseError(response)
  }
  const blob = await response.blob()
  return URL.createObjectURL(blob)
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const token = getAccessToken()
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (response.status === 401) {
    handleUnauthorized(token)
  }
  if (!response.ok) {
    throw await parseError(response)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
