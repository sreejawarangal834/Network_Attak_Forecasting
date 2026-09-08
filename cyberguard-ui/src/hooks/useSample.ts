/**
 * useSample.ts — Convenience hook combining sample context + prediction data.
 */

import { useMemo } from 'react'
import { useSampleContext } from '../context/SampleContext'
import { useApi } from './useApi'
import { getPrediction, getForecast } from '../services/api'

export function useSampleData() {
  const { sampleId, refreshToken } = useSampleContext()

  const predDeps = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const prediction = useApi(() => getPrediction(sampleId), predDeps)
  const forecast   = useApi(() => getForecast(sampleId),   predDeps)

  return { sampleId, prediction, forecast }
}
