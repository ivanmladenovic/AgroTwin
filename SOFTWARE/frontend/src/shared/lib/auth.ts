const TOKEN_KEY = 'agrotwin.access_token'
const AUTH_EVENT = 'agrotwin:auth'

function notifyAuthChange(): void {
  window.dispatchEvent(new Event(AUTH_EVENT))
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  notifyAuthChange()
}

export function clearAccessToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  notifyAuthChange()
}

export function expireAccessToken(sentToken: string | null): boolean {
  if (!sentToken || getAccessToken() !== sentToken) {
    return false
  }
  clearAccessToken()
  return true
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken())
}

export function subscribeAuth(listener: () => void): () => void {
  window.addEventListener(AUTH_EVENT, listener)
  window.addEventListener('storage', listener)
  return () => {
    window.removeEventListener(AUTH_EVENT, listener)
    window.removeEventListener('storage', listener)
  }
}
