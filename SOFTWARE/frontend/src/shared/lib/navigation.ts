import { useCallback } from 'react'
import { useNavigate, type NavigateOptions, type To } from 'react-router-dom'

/** React Router keeps a stack index on history.state.idx. */
export function canGoBackInApp() {
  const idx = (window.history.state as { idx?: number } | null)?.idx
  return typeof idx === 'number' && idx > 0
}

export function useSmartBack(fallback: To = '/') {
  const navigate = useNavigate()

  return useCallback(
    (options?: NavigateOptions) => {
      if (canGoBackInApp()) {
        navigate(-1)
        return
      }
      navigate(fallback, options)
    },
    [fallback, navigate],
  )
}

/** Query params that are page chrome (selection/filter), not a new “place” to restore scroll for. */
const SCROLL_IGNORE_PARAMS = new Set(['tree', 'health', 'map', 'row'])

export function locationKey(pathname: string, search: string) {
  if (!search || search === '?') return pathname
  const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
  for (const key of SCROLL_IGNORE_PARAMS) params.delete(key)
  const kept = params.toString()
  return kept ? `${pathname}?${kept}` : pathname
}
