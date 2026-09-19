import { apiRequest } from '@/shared/lib/api'
import type { TokenResponse, User } from '@/shared/api/types'
import type { LoginValues } from '@/features/auth/schemas'

export function login(values: LoginValues) {
  return apiRequest<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(values),
    skipAuth: true,
  })
}

export function getCurrentUser() {
  return apiRequest<User>('/auth/me')
}
