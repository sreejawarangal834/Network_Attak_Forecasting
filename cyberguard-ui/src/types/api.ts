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

/**
 * Actual backend response shape:
 * { "sample_id": 100, "states": [ { step, features }, ... ] }
 * The array is under the "states" key, not the response root.
 */
export interface ForecastStatesResponse {
  sample_id: number
  states: ForecastStateStep[]
}

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
  Attack_Accuracy: number | string
  Attack_Precision: number | string   // "N/A" for models that don't compute it
  Attack_Recall: number | string
  Attack_F1: number | string
  Stage_Accuracy: number | string
  Stage_Macro_F1: number | string
  [key: string]: number | string      // allow extra columns added in future
}

/**
 * Actual backend response: a plain JSON array — NOT { value, Count }.
 * The endpoint does `df.fillna("N/A").to_dict(orient="records")` which
 * returns the array directly at the response root.
 *
 * ModelPerformance.tsx handles both the array form (correct) and the legacy
 * wrapped form defensively.
 */
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

// ── POST /upload ──────────────────────────────────────────────────────────────
/**
 * Backend supports CSV only. PCAP/PCAPNG are explicitly NOT supported.
 * Confirmed from upload_validator.py: ALLOWED_EXTENSIONS = {".csv"}
 */
export interface UploadResponse {
  upload_id:   string
  filename:    string
  size_bytes:  number
  file_type:   string | null   // "packet" | "flow" | "unknown" | null
  rows:        number
  status:      string          // "validated"
  message:     string
  has_labels:  boolean
}

// ── POST /analyze/{upload_id} / GET /analysis/{id} ───────────────────────────

export interface AnalysisInput {
  filename:     string
  records:      number
  time_windows: number
  ts_start:     string
  ts_end:       string
  file_type:    string
}

export interface UploadCurrentState {
  stage:              string
  attack_probability: number
  risk:               string
  stage_confidence:   number
  mitre_attack_id:    string | null
  mitre_attack_name:  string | null
}

export interface UploadForecastStep {
  step:               number
  attack_probability: number
  risk:               string
  stage:              string
  stage_confidence:   number
  mitre_attack_id:    string | null
  mitre_attack_name:  string | null
}

export interface UploadExplainFeature {
  feature:     string
  sensitivity: number
}

export interface UploadEvalMetrics {
  attack_accuracy:  number | null
  attack_precision: number | null
  attack_recall:    number | null
  attack_f1:        number | null
}

export interface AnalysisResponse {
  analysis_id:    string
  status:         string
  input:          AnalysisInput
  current_state:  UploadCurrentState
  forecast:       UploadForecastStep[]
  explainability: UploadExplainFeature[]
  metrics:        UploadEvalMetrics | null
}

// ── GET /analysis/{id}/states ─────────────────────────────────────────────────

export interface WindowStateOut {
  window_index:  number
  window_start:  string
  record_count:  number
  features:      Record<string, number>
}

export interface UploadStatesResponse {
  analysis_id:  string
  time_windows: number
  states:       WindowStateOut[]
}

// ── GET /analysis/{id}/entities ───────────────────────────────────────────────

/**
 * A single forecast step inside the entity trajectory.
 * Same shape as UploadForecastStep but also carried inside EntityRecord.
 */
export interface EntityTrajectoryStep {
  step:               number
  stage:              string
  attack_probability: number
  stage_confidence:   number
  risk:               string
  mitre_attack_id:    string | null
  mitre_attack_name:  string | null
}

/**
 * A single monitored endpoint extracted from the uploaded telemetry.
 *
 * NOTE — prediction_scope is always "network-level".  The current model
 * was trained on network-aggregated states; attack_probability / risk /
 * predicted_stage are the network-level inference result applied uniformly
 * to all entities visible in the capture.  They are NOT per-entity model
 * predictions.
 */
export interface EntityRecord {
  entity_id:          string        // e.g. "192.168.1.10"
  record_count:       number        // rows in upload where this IP appears
  first_seen:         string
  last_seen:          string
  unique_dst_ips:     string[]
  unique_dst_ports:   number[]
  protocols:          string[]
  // Network-level inference values (uniform across all entities)
  attack_probability: number
  risk:               string        // "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  highest_risk:       string
  predicted_stage:    string
  stage_confidence:   number
  mitre_attack_id:    string | null
  mitre_attack_name:  string | null
  trajectory:         EntityTrajectoryStep[]
  prediction_scope:   'network-level'
}

/** Network-level inference summary (always present, regardless of entity IDs). */
export interface NetworkPrediction {
  attack_probability: number
  risk:               string
  highest_risk:       string
  predicted_stage:    string
  stage_confidence:   number
  mitre_attack_id:    string | null
  mitre_attack_name:  string | null
  trajectory:         EntityTrajectoryStep[]
}

/**
 * GET /analysis/{id}/entities response.
 *
 * When has_entity_ids=false the entities array is empty and the caller
 * must label the view "NETWORK-LEVEL PREDICTION".
 * When has_entity_ids=true, entities contains the discovered endpoints;
 * their risk/stage values are still network-level (prediction_scope field).
 */
export interface EntitiesResponse {
  analysis_id:      string
  has_entity_ids:   boolean
  prediction_scope: 'network-level'
  total_entities:   number
  // Only present when has_entity_ids=true
  normal_count?:     number
  suspicious_count?: number
  high_risk_count?:  number
  entities:          EntityRecord[]
  network_prediction: NetworkPrediction
}

// ── GET /alerts/status ────────────────────────────────────────────────────────
export interface AlertStatusResponse {
  enabled:              boolean
  configured:           boolean
  recipient_configured: boolean
  smtp_configured:      boolean
}

// ── POST /alerts/test ─────────────────────────────────────────────────────────
export interface AlertTestResponse {
  success: boolean
  message: string
}

// ── GET /runs ─────────────────────────────────────────────────────────────────

/**
 * One forecast step from a stored run.
 * Mirrors RunForecastStep Pydantic model in main.py.
 */
export interface RunForecastStep {
  step:               number
  attack_probability: number
  risk_level:         string
  predicted_stage:    string
  stage_confidence:   number
  mitre_id:           string | null
  mitre_technique:    string | null
}

/**
 * One feature sensitivity entry from a stored run.
 */
export interface RunExplainFeature {
  rank:         number
  feature_name: string
  sensitivity:  number
}

/**
 * Lightweight run row — returned by GET /runs.
 * Does NOT include forecast steps or explainability.
 */
export interface RunSummary {
  run_id:             string
  created_at:         string
  source_type:        string          // 'uploaded' | 'sample'
  filename:           string | null
  status:             string
  attack_probability: number
  risk_level:         string
  predicted_stage:    string
  stage_confidence:   number
  mitre_id:           string | null
  mitre_technique:    string | null
  file_type:          string | null
  total_records:      number | null
  total_windows:      number | null
  ts_start:           string | null
  ts_end:             string | null
}

/**
 * Full run detail — returned by GET /runs/{run_id}.
 * Extends RunSummary with forecast steps, explainability, and optional metrics.
 */
export interface RunDetail extends RunSummary {
  forecast:       RunForecastStep[]
  explainability: RunExplainFeature[]
  metrics:        Record<string, number | null> | null
}
