/**
 * api.ts — TypeScript interfaces matching the FastAPI backend contract.
 *
 * These types are derived solely from the documented API response shapes.
 * Do NOT add fields that the backend does not return.
 *
 * Backend:  python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
 * Swagger:  http://127.0.0.1:8000/docs
 */

// ── GET /health ───────────────────────────────────────────────────────────────
export interface HealthResponse {
  status: string           // e.g. "healthy"
  model: string            // e.g. "Temporal Transformer World Model"
  device: string           // e.g. "cpu"
  input_shape: [number, number] // e.g. [5, 44]
}

// ── GET /model/info ───────────────────────────────────────────────────────────
export interface ModelInfoResponse {
  model_type: string           // e.g. "Temporal Transformer"
  device: string               // e.g. "cpu"
  sequence_length: number      // e.g. 5
  num_features: number         // e.g. 44
  num_stages: number           // e.g. 5
  parameters: number           // e.g. 81650
  autoregressive_horizon: number // e.g. 5
}

// ── GET /samples ──────────────────────────────────────────────────────────────
export interface SamplesResponse {
  num_test_samples: number     // e.g. 654
  sequence_length: number      // e.g. 5
  num_features: number         // e.g. 44
  stages: string[]             // ["Benign","Reconnaissance",...]
}

// ── GET /predict/{sample_id} ──────────────────────────────────────────────────
export interface PredictionResponse {
  sample_id: number
  /** Ground-truth stage for this sample (reference context, NOT a model output). */
  current_true_stage: string
  attack_probability: number    // 0–1
  attack_detected: boolean
  predicted_stage: string
  stage_confidence: number      // 0–1
  mitre_attack_id: string       // e.g. "T1595"
  mitre_attack_name: string     // e.g. "Active Scanning"
}

// ── GET /forecast/{sample_id} ────────────────────────────────────────────────
export interface ForecastStep {
  step: number
  stage: string
  attack_probability: number
  attack_detected: boolean
  stage_confidence: number
  mitre_attack_id: string
  mitre_attack_name: string
}

export interface ForecastResponse {
  sample_id: number
  horizon: number
  /** Whether ground-truth was used — important World Model property. */
  ground_truth_used: boolean
  forecast: ForecastStep[]
}

// ── GET /forecast/{sample_id}/states ─────────────────────────────────────────
export interface ForecastStateStep {
  step: number
  features: Record<string, number>
}

export type ForecastStatesResponse = ForecastStateStep[]

// ── GET /explain/{sample_id} ──────────────────────────────────────────────────
export interface ExplanationFeature {
  rank: number
  feature: string
  sensitivity: number
}

export interface ExplanationResponse {
  sample_id: number
  /** Explanation method used by the backend. */
  method: string
  /** Backend-supplied warning — must be shown to users. */
  warning: string
  features: ExplanationFeature[]
}

// ── GET /model/comparison ────────────────────────────────────────────────────
export interface ComparisonRow {
  Model: string
  Temporal_History: number | string
  Attack_Accuracy: number
  Attack_Precision: number
  Attack_Recall: number
  Attack_F1: number
  Stage_Accuracy: number
  Stage_Macro_F1: number
}

export type ModelComparisonResponse = ComparisonRow[]

// ── Shared utility types ──────────────────────────────────────────────────────

/** Possible attack stages — matches backend /samples response. */
export type AttackStage =
  | 'Benign'
  | 'Reconnaissance'
  | 'BruteForce'
  | 'LateralMovement'
  | 'CommandAndControl'

/** API call wrapper used by hooks. */
export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}
