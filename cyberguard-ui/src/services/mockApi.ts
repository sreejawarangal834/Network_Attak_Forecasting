/**
 * mockApi.ts — Isolated fallback mock service.
 *
 * Used ONLY when the FastAPI backend is unavailable during development.
 * All values are clearly labelled as mock/demo data.
 *
 * TO DISABLE MOCKS: set VITE_USE_MOCK=false in .env (default: false)
 * The real api.ts is always the primary implementation.
 *
 * When the backend is running, these functions are never called.
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

const DELAY = 400 // simulated network latency (ms)
const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

export const MOCK_STAGES = [
  'Benign',
  'Reconnaissance',
  'BruteForce',
  'LateralMovement',
  'CommandAndControl',
]

export async function mockGetHealth(): Promise<HealthResponse> {
  await sleep(DELAY)
  return {
    status: 'healthy (MOCK)',
    model: 'Temporal Transformer World Model',
    device: 'cpu',
    input_shape: [5, 44],
  }
}

export async function mockGetModelInfo(): Promise<ModelInfoResponse> {
  await sleep(DELAY)
  return {
    model_type: 'Temporal Transformer',
    device: 'cpu',
    sequence_length: 5,
    num_features: 44,
    num_stages: 5,
    parameters: 81650,
    autoregressive_horizon: 5,
  }
}

export async function mockGetSamples(): Promise<SamplesResponse> {
  await sleep(DELAY)
  return {
    num_test_samples: 654,
    sequence_length: 5,
    num_features: 44,
    stages: MOCK_STAGES,
  }
}

export async function mockGetPrediction(sampleId: number): Promise<PredictionResponse> {
  await sleep(DELAY)
  return {
    sample_id: sampleId,
    current_true_stage: 'Reconnaissance',
    attack_probability: 0.9822,
    attack_detected: true,
    predicted_stage: 'Reconnaissance',
    stage_confidence: 0.8992,
    mitre_attack_id: 'T1595',
    mitre_attack_name: 'Active Scanning',
  }
}

export async function mockGetForecast(sampleId: number): Promise<ForecastResponse> {
  await sleep(DELAY)
  return {
    sample_id: sampleId,
    horizon: 5,
    ground_truth_used: false,
    forecast: [
      { step: 1, stage: 'Reconnaissance',     attack_probability: 0.9822, attack_detected: true,  stage_confidence: 0.8992, mitre_attack_id: 'T1595', mitre_attack_name: 'Active Scanning' },
      { step: 2, stage: 'BruteForce',          attack_probability: 0.9641, attack_detected: true,  stage_confidence: 0.8140, mitre_attack_id: 'T1110', mitre_attack_name: 'Brute Force' },
      { step: 3, stage: 'LateralMovement',     attack_probability: 0.9510, attack_detected: true,  stage_confidence: 0.7820, mitre_attack_id: 'T1021', mitre_attack_name: 'Remote Services' },
      { step: 4, stage: 'CommandAndControl',   attack_probability: 0.9301, attack_detected: true,  stage_confidence: 0.7550, mitre_attack_id: 'T1071', mitre_attack_name: 'Application Layer Protocol' },
      { step: 5, stage: 'CommandAndControl',   attack_probability: 0.9180, attack_detected: true,  stage_confidence: 0.7210, mitre_attack_id: 'T1071', mitre_attack_name: 'Application Layer Protocol' },
    ],
  }
}

export async function mockGetForecastStates(sampleId: number): Promise<ForecastStatesResponse> {
  await sleep(DELAY)
  // Produce 5 steps × 44 placeholder features
  const featureNames = Array.from({ length: 44 }, (_, i) => `feature_${i + 1}`)
  return Array.from({ length: 5 }, (_, stepIdx) => ({
    step: stepIdx + 1,
    features: Object.fromEntries(
      featureNames.map(name => [name, parseFloat((Math.random() * 100).toFixed(4))])
    ),
  }))
  // suppress sampleId-unused warning
  void sampleId
}

export async function mockGetExplanation(sampleId: number): Promise<ExplanationResponse> {
  await sleep(DELAY)
  void sampleId
  return {
    sample_id: sampleId,
    method: 'feature_ablation_sensitivity (MOCK)',
    warning: 'Sensitivity indicates prediction influence and does not establish causation.',
    features: [
      { rank: 1,  feature: 'ack_to_packet_ratio',     sensitivity: 0.025616 },
      { rank: 2,  feature: 'syn_flag_rate',            sensitivity: 0.021840 },
      { rank: 3,  feature: 'dst_port_entropy',         sensitivity: 0.019200 },
      { rank: 4,  feature: 'packet_size_variance',     sensitivity: 0.016750 },
      { rank: 5,  feature: 'flow_duration',            sensitivity: 0.014310 },
      { rank: 6,  feature: 'bytes_per_second',         sensitivity: 0.012900 },
      { rank: 7,  feature: 'ttl_variation',            sensitivity: 0.011450 },
      { rank: 8,  feature: 'rst_flag_rate',            sensitivity: 0.009820 },
      { rank: 9,  feature: 'unique_dst_ports',         sensitivity: 0.008710 },
      { rank: 10, feature: 'inter_arrival_time_mean',  sensitivity: 0.007640 },
    ],
  }
}

export async function mockGetModelComparison(): Promise<ModelComparisonResponse> {
  await sleep(DELAY)
  return [
    {
      Model: 'Temporal Transformer (MOCK)',
      Temporal_History: 5,
      Attack_Accuracy: 0.9412,
      Attack_Precision: 0.9380,
      Attack_Recall: 0.9460,
      Attack_F1: 0.9420,
      Stage_Accuracy: 0.8890,
      Stage_Macro_F1: 0.8760,
    },
    {
      Model: 'Logistic Regression (MOCK)',
      Temporal_History: 1,
      Attack_Accuracy: 0.8120,
      Attack_Precision: 0.8050,
      Attack_Recall: 0.8220,
      Attack_F1: 0.8130,
      Stage_Accuracy: 0.6710,
      Stage_Macro_F1: 0.6480,
    },
  ]
}
