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
