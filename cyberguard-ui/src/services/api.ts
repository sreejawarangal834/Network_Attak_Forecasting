/**
 * api.ts — Primary API service layer.
 *
 * All network requests go through this module — never call fetch() directly
 * in components. This keeps the API contract in one place and makes mocking
 * or backend URL changes trivially easy.
 *
 * Base URL is read from the Vite env variable VITE_API_BASE_URL.
 * In development the Vite proxy rewrites /api/* → http://127.0.0.1:8000/*,
 * so direct calls work too, but we use the env var for production builds.
 */

import type {
  HealthResponse,
  ModelInfoResponse,
  SamplesResponse,
  PredictionResponse,
  ForecastResponse,
  ForecastStatesResponse,
  ExplanationResponse,
  ModelComparisonResponse,
} from '../types/api'

// ── Configuration ─────────────────────────────────────────────────────────────
const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)
  ?? 'http://127.0.0.1:8000'

const DEFAULT_TIMEOUT_MS = 10_000

// ── Core fetch wrapper ────────────────────────────────────────────────────────

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly endpoint?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(endpoint: string): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)

  try {
    const url = `${BASE_URL}${endpoint}`
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })

    if (!res.ok) {
      throw new ApiError(
        `HTTP ${res.status}: ${res.statusText}`,
        res.status,
        endpoint,
      )
    }

    return (await res.json()) as T
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${DEFAULT_TIMEOUT_MS}ms`, undefined, endpoint)
    }
    // Network error (backend offline, CORS, etc.)
    throw new ApiError(
      `Unable to reach backend at ${BASE_URL}. Is FastAPI running?`,
      undefined,
      endpoint,
    )
  } finally {
    clearTimeout(timer)
  }
}

// ── Public API functions ──────────────────────────────────────────────────────

/** GET /health — Check backend and model status. */
export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

/** GET /model/info — Model architecture details. */
export async function getModelInfo(): Promise<ModelInfoResponse> {
  return request<ModelInfoResponse>('/model/info')
}

/** GET /samples — Dataset and stage metadata. */
export async function getSamples(): Promise<SamplesResponse> {
  return request<SamplesResponse>('/samples')
}

/**
 * GET /predict/{sample_id} — Single-step prediction for a sample.
 * Note: current_true_stage is ground-truth context, not a model prediction.
 */
export async function getPrediction(sampleId: number): Promise<PredictionResponse> {
  return request<PredictionResponse>(`/predict/${sampleId}`)
}

/**
 * GET /forecast/{sample_id} — 5-step autoregressive forecast.
 * ground_truth_used will be false for genuine autoregressive operation.
 */
export async function getForecast(sampleId: number): Promise<ForecastResponse> {
  return request<ForecastResponse>(`/forecast/${sampleId}`)
}

/**
 * GET /forecast/{sample_id}/states — 44-feature predicted network states
 * for each of the 5 forecast steps.
 */
export async function getForecastStates(sampleId: number): Promise<ForecastStatesResponse> {
  return request<ForecastStatesResponse>(`/forecast/${sampleId}/states`)
}

/**
 * GET /explain/{sample_id} — Feature sensitivity analysis.
 * Sensitivity indicates prediction influence, NOT causation (backend warning).
 */
export async function getExplanation(sampleId: number): Promise<ExplanationResponse> {
  return request<ExplanationResponse>(`/explain/${sampleId}`)
}

/** GET /model/comparison — Performance comparison table. */
export async function getModelComparison(): Promise<ModelComparisonResponse> {
  return request<ModelComparisonResponse>('/model/comparison')
}

export { ApiError, BASE_URL }

// ── Upload workflow ────────────────────────────────────────────────────────────

import type {
  UploadResponse,
  AnalysisResponse,
  UploadStatesResponse,
  EntitiesResponse,
  UploadForecastStep,
  UploadExplainFeature,
} from '../types/api'

/**
 * POST /upload — Upload a CSV telemetry file.
 * Only .csv is supported by the backend (no PCAP/PCAPNG).
 * Returns an upload_id for the subsequent /analyze call.
 */
export async function uploadFile(file: File): Promise<UploadResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60_000) // 60s for upload

  try {
    const form = new FormData()
    form.append('file', file)

    const url = `${BASE_URL}/upload`
    const res = await fetch(url, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    })

    if (!res.ok) {
      // Backend returns structured error details
      let detail = `HTTP ${res.status}: ${res.statusText}`
      try {
        const body = await res.json() as { detail?: unknown }
        if (typeof body.detail === 'string') detail = body.detail
        else if (Array.isArray(body.detail)) {
          detail = (body.detail as Array<{ message?: string }>)
            .map(e => e.message ?? JSON.stringify(e)).join('; ')
        } else if (body.detail) {
          const d = body.detail as { message?: string }
          if (d.message) detail = d.message
        }
      } catch { /* ignore parse errors */ }
      throw new ApiError(detail, res.status, '/upload')
    }

    return (await res.json()) as UploadResponse
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Upload timed out after 60 seconds', undefined, '/upload')
    }
    throw new ApiError(
      `Unable to reach backend at ${BASE_URL}. Is FastAPI running?`,
      undefined, '/upload',
    )
  } finally {
    clearTimeout(timer)
  }
}

/**
 * POST /analyze/{upload_id} — Run the full pipeline on an uploaded file.
 * Builds 44-feature time windows, runs inference + autoregressive rollout.
 * May take several seconds for large files.
 */
export async function analyzeUpload(uploadId: string): Promise<AnalysisResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 120_000) // 2 min for pipeline

  try {
    const res = await fetch(`${BASE_URL}/analyze/${uploadId}`, {
      method: 'POST',
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}: ${res.statusText}`
      try {
        const body = await res.json() as { detail?: unknown }
        if (typeof body.detail === 'string') detail = body.detail
        else if (Array.isArray(body.detail)) {
          detail = (body.detail as Array<{ message?: string }>)
            .map(e => e.message ?? JSON.stringify(e)).join('; ')
        }
      } catch { /* ignore */ }
      throw new ApiError(detail, res.status, `/analyze/${uploadId}`)
    }
    return (await res.json()) as AnalysisResponse
  } catch (err) {
    if (err instanceof ApiError) throw err
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('Analysis timed out. The file may be too large.', undefined, `/analyze/${uploadId}`)
    }
    throw new ApiError(`Unable to reach backend at ${BASE_URL}.`, undefined, `/analyze/${uploadId}`)
  } finally {
    clearTimeout(timer)
  }
}

/** GET /analysis/{id} — Retrieve a cached analysis result. */
export async function getAnalysis(analysisId: string): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(`/analysis/${analysisId}`)
}

/** GET /analysis/{id}/states — Retrieve time-window feature states. */
export async function getAnalysisStates(analysisId: string): Promise<UploadStatesResponse> {
  return request<UploadStatesResponse>(`/analysis/${analysisId}/states`)
}

/**
 * GET /analysis/{id}/entities — Return monitored entities and their risk.
 *
 * prediction_scope is always "network-level" — the current model was
 * trained on network-aggregated states and does not produce per-entity
 * predictions.  When has_entity_ids=false the caller must label the
 * view "NETWORK-LEVEL PREDICTION".
 */
export async function getAnalysisEntities(analysisId: string): Promise<EntitiesResponse> {
  return request<EntitiesResponse>(`/analysis/${analysisId}/entities`)
}

/**
 * GET /analysis/{id}/forecast — 5-step forecast from a completed analysis.
 * Returns the same forecast that was computed at analysis time.
 */
export async function getAnalysisForecastResult(analysisId: string): Promise<{
  analysis_id: string
  horizon: number
  ground_truth_used: boolean
  forecast: UploadForecastStep[]
}> {
  return request(`/analysis/${analysisId}/forecast`)
}

/**
 * GET /analysis/{id}/explain — Feature sensitivity for a completed analysis.
 */
export async function getAnalysisExplain(analysisId: string): Promise<{
  analysis_id: string
  method: string
  warning: string
  features: UploadExplainFeature[]
}> {
  return request(`/analysis/${analysisId}/explain`)
}

// ── Alert endpoints ────────────────────────────────────────────────────────────

import type { AlertStatusResponse, AlertTestResponse } from '../types/api'

/** GET /alerts/status — Email alert configuration status. */
export async function getAlertStatus(): Promise<AlertStatusResponse> {
  return request<AlertStatusResponse>('/alerts/status')
}

/** POST /alerts/test — Send a test email alert. */
export async function testAlert(): Promise<AlertTestResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 20_000)
  try {
    const res = await fetch(`${BASE_URL}/alerts/test`, {
      method: 'POST',
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string }
      throw new ApiError(body.detail ?? `HTTP ${res.status}`, res.status, '/alerts/test')
    }
    return (await res.json()) as AlertTestResponse
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError('Unable to reach backend.', undefined, '/alerts/test')
  } finally {
    clearTimeout(timer)
  }
}

// ── Prediction run history ─────────────────────────────────────────────────────

import type { RunSummary, RunDetail, RunForecastStep } from '../types/api'

/**
 * GET /runs?limit=N — Return recent prediction runs from SQLite.
 * Survives backend restarts — data comes from disk, not in-memory store.
 */
export async function getRuns(limit = 50): Promise<RunSummary[]> {
  return request<RunSummary[]>(`/runs?limit=${encodeURIComponent(limit)}`)
}

/**
 * GET /runs/{run_id} — Full prediction detail for one stored run,
 * including all 5 forecast steps and top feature sensitivity scores.
 */
export async function getRunDetail(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${encodeURIComponent(runId)}`)
}

/**
 * GET /runs/{run_id}/forecast — Just the 5 autoregressive forecast steps.
 */
export async function getRunForecast(runId: string): Promise<RunForecastStep[]> {
  return request<RunForecastStep[]>(`/runs/${encodeURIComponent(runId)}/forecast`)
}
