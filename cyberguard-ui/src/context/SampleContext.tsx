/**
 * SampleContext.tsx — Global selected sample state.
 *
 * Every page that needs the current sample ID reads it from here.
 * Changing the sample triggers a re-fetch on all subscribed pages.
 */

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { DEFAULT_SAMPLE_ID } from '../utils/constants'

interface SampleContextValue {
  sampleId: number
  maxSamples: number
  setSampleId: (id: number) => void
  setMaxSamples: (n: number) => void
  /** Increment a counter to force data re-fetch without changing sample. */
  refresh: () => void
  refreshToken: number
}

const SampleContext = createContext<SampleContextValue | null>(null)

export function SampleProvider({ children }: { children: ReactNode }) {
  const [sampleId, setSampleIdRaw]   = useState(DEFAULT_SAMPLE_ID)
  const [maxSamples, setMaxSamples]  = useState(654)
  const [refreshToken, setRefreshToken] = useState(0)

  const setSampleId = useCallback((id: number) => {
    setSampleIdRaw(Math.max(0, Math.min(id, maxSamples - 1)))
  }, [maxSamples])

  const refresh = useCallback(() => {
    setRefreshToken(t => t + 1)
  }, [])

  return (
    <SampleContext.Provider value={{
      sampleId, maxSamples,
      setSampleId, setMaxSamples,
      refresh, refreshToken,
    }}>
      {children}
    </SampleContext.Provider>
  )
}

export function useSampleContext(): SampleContextValue {
  const ctx = useContext(SampleContext)
  if (!ctx) throw new Error('useSampleContext must be used inside <SampleProvider>')
  return ctx
}
