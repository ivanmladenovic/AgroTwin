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

export function locationKey(pathname: string, search: string) {
  return `${pathname}${search}`
}
