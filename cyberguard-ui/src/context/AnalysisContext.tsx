/**
 * AnalysisContext.tsx — Global active-analysis state with sessionStorage persistence.
 *
 * Persistence strategy
 * --------------------
 * When an analysis completes:
 *   - analysis_id is written to sessionStorage under STORAGE_KEY
 *   - full AnalysisResponse + EntitiesResponse are written to sessionStorage under
 *     STORAGE_DATA_KEY so a refresh never needs to hit the backend again within
 *     the same browser session.
 *
 * On mount (app startup / browser refresh):
 *   - Read STORAGE_KEY to get the saved analysis_id.
 *   - Read STORAGE_DATA_KEY to restore the cached response immediately.
 *   - If cached data exists → restore instantly (no spinner, no flash of demo view).
 *   - If cache is missing but id exists → fetch from backend (backend restart case).
 *   - If backend returns 404 → mark as "analysis_expired" so UI can show the
 *     "Analysis expired / unavailable" state instead of silently falling back to
 *     Sample #100.
 *
 * Navigation safety
 * -----------------
 * All state lives here, mounted once at the application root in App.tsx.
 * As long as navigation uses React Router <Link>/<Navigate>/useNavigate (not
 * <a href> or window.location), the provider is never unmounted and state
 * survives every route change.
 *
 * The legacy SampleContext-based developer/demo fallback is untouched.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react'
import type { AnalysisResponse, EntitiesResponse, EntityRecord } from '../types/api'
import { getAnalysis, getAnalysisEntities } from '../services/api'
import { ApiError } from '../services/api'

// ── Storage keys ──────────────────────────────────────────────────────────────
const STORAGE_KEY      = 'cyberguard_active_analysis_id'
const STORAGE_DATA_KEY = 'cyberguard_active_analysis_data'

// ── Restore status ────────────────────────────────────────────────────────────
export type RestoreStatus =
  | 'idle'        // never attempted (initial render still in progress)
  | 'restoring'   // fetching from backend after refresh
  | 'restored'    // successfully loaded from cache or backend
  | 'expired'     // analysis_id found in storage but backend no longer has it
  | 'none'        // no stored analysis_id — fresh session

// ── Context value shape ───────────────────────────────────────────────────────

export interface AnalysisContextValue {
  /** The raw AnalysisResponse — null until first upload or restore. */
  analysis:        AnalysisResponse | null
  /** The EntitiesResponse — null until fetched. */
  entitiesData:    EntitiesResponse | null
  /** True while an upload+analysis pipeline is in progress. */
  analysisLoading: boolean
  /** Error from the last analysis attempt (pipeline errors, not restore errors). */
  analysisError:   string | null
  /** The entity_id the user has selected. null = network-level view. */
  selectedEntityId: string | null
  /** Restore status — used to distinguish "loading" from "no analysis". */
  restoreStatus:   RestoreStatus

  // ── Setters (called by DatasetUpload) ──────────────────────────────────────
  setAnalysis:        (a: AnalysisResponse | null) => void
  setEntitiesData:    (e: EntitiesResponse | null) => void
  setAnalysisLoading: (v: boolean) => void
  setAnalysisError:   (msg: string | null) => void
  selectEntity:       (id: string | null) => void
  resetAnalysis:      () => void

  // ── Derived ───────────────────────────────────────────────────────────────
  selectedEntity: EntityRecord | null
  hasAnalysis:    boolean
  analysisLabel:  string
  analysisId:     string | null
  /**
   * True while the initial restore is still in progress (restoreStatus === 'restoring'
   * or 'idle').  Pages should show a loading skeleton rather than the upload prompt
   * during this window so there is no flash of the demo view.
   */
  isRestoring:    boolean
}

// ── Context ───────────────────────────────────────────────────────────────────
const AnalysisContext = createContext<AnalysisContextValue | null>(null)

// ── Helpers ───────────────────────────────────────────────────────────────────

function readStoredId(): string | null {
  try { return sessionStorage.getItem(STORAGE_KEY) } catch { return null }
}

function writeStoredId(id: string | null): void {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id)
    else    sessionStorage.removeItem(STORAGE_KEY)
  } catch { /* storage unavailable */ }
}

interface StoredData {
  analysis:     AnalysisResponse
  entitiesData: EntitiesResponse | null
}

function readStoredData(): StoredData | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_DATA_KEY)
    if (!raw) return null
    return JSON.parse(raw) as StoredData
  } catch { return null }
}

function writeStoredData(d: StoredData | null): void {
  try {
    if (d) sessionStorage.setItem(STORAGE_DATA_KEY, JSON.stringify(d))
    else   sessionStorage.removeItem(STORAGE_DATA_KEY)
  } catch { /* storage quota exceeded or unavailable — not fatal */ }
}

function clearStorage(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
    sessionStorage.removeItem(STORAGE_DATA_KEY)
  } catch { /* ignore */ }
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function AnalysisProvider({ children }: { children: ReactNode }) {
  const [analysis,         setAnalysisRaw]     = useState<AnalysisResponse | null>(null)
  const [entitiesData,     setEntitiesRaw]     = useState<EntitiesResponse | null>(null)
  const [analysisLoading,  setAnalysisLoading] = useState(false)
  const [analysisError,    setAnalysisError]   = useState<string | null>(null)
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null)
  const [restoreStatus,    setRestoreStatus]   = useState<RestoreStatus>('idle')

  // ── Startup restore ───────────────────────────────────────────────────────
  useEffect(() => {
    const storedId = readStoredId()

    if (!storedId) {
      console.debug('[AnalysisContext] no stored analysis — fresh session')
      setRestoreStatus('none')
      return
    }

    // Try to restore from cached data first (instant, no network)
    const cached = readStoredData()
    if (cached?.analysis?.analysis_id === storedId) {
      setAnalysisRaw(cached.analysis)
      setEntitiesRaw(cached.entitiesData ?? null)
      setRestoreStatus('restored')
      console.debug('[AnalysisContext] restored analysis from cache:', storedId)
      return
    }

    // Cache miss — fetch from backend (handles backend restart)
    setRestoreStatus('restoring')
    console.debug('[AnalysisContext] fetching analysis from backend:', storedId)

    ;(async () => {
      try {
        const [analysisResult, entitiesResult] = await Promise.allSettled([
          getAnalysis(storedId),
          getAnalysisEntities(storedId),
        ])

        if (analysisResult.status === 'rejected') {
          const err = analysisResult.reason
          // 404 = analysis expired from in-memory store after backend restart
          const is404 = err instanceof ApiError && err.status === 404
          if (is404) {
            console.debug('[AnalysisContext] analysis expired (404):', storedId)
            clearStorage()
            setRestoreStatus('expired')
          } else {
            // Network error — keep stored id, show error
            console.debug('[AnalysisContext] restore failed (network):', err)
            clearStorage()
            setRestoreStatus('none')
          }
          return
        }

        const restoredAnalysis = analysisResult.value
        const restoredEntities = entitiesResult.status === 'fulfilled'
          ? entitiesResult.value
          : null

        setAnalysisRaw(restoredAnalysis)
        setEntitiesRaw(restoredEntities)
        writeStoredData({ analysis: restoredAnalysis, entitiesData: restoredEntities })
        setRestoreStatus('restored')
        console.debug('[AnalysisContext] restored analysis from backend:', storedId)
      } catch (err) {
        console.debug('[AnalysisContext] unexpected restore error:', err)
        clearStorage()
        setRestoreStatus('none')
      }
    })()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // run once on mount only

  // ── Setters ───────────────────────────────────────────────────────────────

  const setAnalysis = useCallback((a: AnalysisResponse | null) => {
    setAnalysisRaw(a)
    setSelectedEntityId(null)
    if (a) {
      writeStoredId(a.analysis_id)
      // Data will be written once entities are also available (see setEntitiesData).
      // Write partial data now so a reload before entities arrive still works.
      writeStoredData({ analysis: a, entitiesData: null })
      setRestoreStatus('restored')
      console.debug('[AnalysisContext] active analysis:', a.analysis_id)
    } else {
      clearStorage()
      setRestoreStatus('none')
      console.debug('[AnalysisContext] cleared analysis')
    }
  }, [])

  const setEntitiesData = useCallback((e: EntitiesResponse | null) => {
    setEntitiesRaw(e)
    // Re-persist with entities so restore includes them
    setAnalysisRaw(prev => {
      if (prev) writeStoredData({ analysis: prev, entitiesData: e })
      return prev
    })
  }, [])

  const selectEntity = useCallback((id: string | null) => {
    setSelectedEntityId(id)
  }, [])

  const resetAnalysis = useCallback(() => {
    setAnalysisRaw(null)
    setEntitiesRaw(null)
    setAnalysisLoading(false)
    setAnalysisError(null)
    setSelectedEntityId(null)
    setRestoreStatus('none')
    clearStorage()
    console.debug('[AnalysisContext] cleared analysis')
  }, [])

  // ── Derived ───────────────────────────────────────────────────────────────

  const selectedEntity: EntityRecord | null =
    selectedEntityId && entitiesData
      ? (entitiesData.entities.find(e => e.entity_id === selectedEntityId) ?? null)
      : null

  const hasAnalysis  = analysis !== null
  const analysisLabel = analysis ? analysis.input.filename : 'No analysis loaded'
  const analysisId    = analysis?.analysis_id ?? null
  const isRestoring   = restoreStatus === 'idle' || restoreStatus === 'restoring'

  const value: AnalysisContextValue = {
    analysis,
    entitiesData,
    analysisLoading,
    analysisError,
    selectedEntityId,
    restoreStatus,
    setAnalysis,
    setEntitiesData,
    setAnalysisLoading,
    setAnalysisError,
    selectEntity,
    resetAnalysis,
    selectedEntity,
    hasAnalysis,
    analysisLabel,
    analysisId,
    isRestoring,
  }

  return (
    <AnalysisContext.Provider value={value}>
      {children}
    </AnalysisContext.Provider>
  )
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

export function useAnalysisContext(): AnalysisContextValue {
  const ctx = useContext(AnalysisContext)
  if (!ctx) throw new Error('useAnalysisContext must be used inside <AnalysisProvider>')
  return ctx
}
