import { useEffect, useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getCurrentUser } from '@/features/auth/api'
import { isAuthenticated, subscribeAuth } from '@/shared/lib/auth'

function useAuthFlag(): boolean {
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated())

  useEffect(() => subscribeAuth(() => setAuthenticated(isAuthenticated())), [])

  return authenticated
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const authenticated = useAuthFlag()
  if (!authenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

export function GuestRoute({ children }: { children: ReactNode }) {
  const authenticated = useAuthFlag()
  if (authenticated) {
    return <Navigate to="/" replace />
  }
  return children
}

/** Developer/admin-only routes (e.g. AI Benchmark). Requires is_superuser. */
export function SuperuserRoute({ children }: { children: ReactNode }) {
  const authenticated = useAuthFlag()
  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: getCurrentUser,
    enabled: authenticated,
  })

  if (!authenticated) {
    return <Navigate to="/login" replace />
  }
  if (meQuery.isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Provera pristupa…</div>
  }
  if (meQuery.isError || !meQuery.data?.is_superuser) {
    return <Navigate to="/" replace />
  }
  return children
}
