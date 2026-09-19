import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'

import { isAuthenticated } from '@/shared/lib/auth'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }
  return children
}

export function GuestRoute({ children }: { children: ReactNode }) {
  if (isAuthenticated()) {
    return <Navigate to="/" replace />
  }
  return children
}
