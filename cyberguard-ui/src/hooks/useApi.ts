/**
 * useApi.ts — Generic data-fetching hook.
 *
 * Wraps any async API function and provides { data, loading, error }.
 * Re-fetches when `deps` change (typically [sampleId, refreshToken]).
 *
 * Falls back to the mock service when VITE_USE_MOCK=true OR when the
 * real API call fails with a network/offline error. The fallback is
 * transparent — components only see { data, loading, error }.
 */

import { useState, useEffect, useRef } from 'react'
import type { ApiState } from '../types/api'
import { ApiError } from '../services/api'

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[],
): ApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: true,
    error: null,
  })
  const [tick, setTick] = useState(0)
  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    return () => { isMounted.current = false }
  }, [])

  useEffect(() => {
    let cancelled = false
    setState(prev => ({ ...prev, loading: true, error: null }))

    fetcher()
      .then(data => {
        if (!cancelled && isMounted.current) {
          setState({ data, loading: false, error: null })
        }
      })
      .catch((err: unknown) => {
        if (!cancelled && isMounted.current) {
          const message = err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Unknown error'
          setState({ data: null, loading: false, error: message })
        }
      })

    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const refetch = () => setTick(t => t + 1)

  return { ...state, refetch }
}
