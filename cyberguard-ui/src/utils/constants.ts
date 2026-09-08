/**
 * constants.ts — Shared visual and domain constants.
 */

export const ATTACK_STAGES = [
  'Benign',
  'Reconnaissance',
  'BruteForce',
  'LateralMovement',
  'CommandAndControl',
] as const

export type AttackStageKey = (typeof ATTACK_STAGES)[number]

export const STAGE_COLORS: Record<AttackStageKey, string> = {
  Benign:             '#22c55e',
  Reconnaissance:     '#f59e0b',
  BruteForce:         '#f97316',
  LateralMovement:    '#ef4444',
  CommandAndControl:  '#7c3aed',
}

export const STAGE_BG: Record<AttackStageKey, string> = {
  Benign:             'rgba(34,197,94,0.10)',
  Reconnaissance:     'rgba(245,158,11,0.10)',
  BruteForce:         'rgba(249,115,22,0.10)',
  LateralMovement:    'rgba(239,68,68,0.10)',
  CommandAndControl:  'rgba(124,58,237,0.10)',
}

export const STAGE_ICONS: Record<AttackStageKey, string> = {
  Benign:            '✅',
  Reconnaissance:    '🔍',
  BruteForce:        '🔨',
  LateralMovement:   '↔️',
  CommandAndControl: '☠️',
}

/** MITRE ATT&CK representative mappings — prototype mapping, not direct technique detection. */
export const MITRE_MAP: Record<string, { id: string; name: string }> = {
  Reconnaissance:    { id: 'T1595', name: 'Active Scanning' },
  BruteForce:        { id: 'T1110', name: 'Brute Force' },
  LateralMovement:   { id: 'T1021', name: 'Remote Services' },
  CommandAndControl: { id: 'T1071', name: 'Application Layer Protocol' },
}

export const RISK_LEVELS = {
  LOW:    { label: 'LOW',      color: '#22c55e', min: 0,    max: 0.30 },
  MEDIUM: { label: 'MEDIUM',   color: '#f59e0b', min: 0.30, max: 0.70 },
  HIGH:   { label: 'HIGH',     color: '#ef4444', min: 0.70, max: 1.01 },
} as const

export function getRiskLevel(prob: number) {
  if (prob < 0.30) return RISK_LEVELS.LOW
  if (prob < 0.70) return RISK_LEVELS.MEDIUM
  return RISK_LEVELS.HIGH
}

export function fmtPct(v: number) {
  return `${(v * 100).toFixed(2)}%`
}

export function fmtPctShort(v: number) {
  return `${(v * 100).toFixed(1)}%`
}

/** Default sample ID used on first load. */
export const DEFAULT_SAMPLE_ID = 100
