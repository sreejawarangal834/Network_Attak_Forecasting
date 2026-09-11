/**
 * Dashboard.tsx — Primary SOC overview page.
 *
 * PRIMARY MODE (when an analysis has been uploaded):
 *   Driven entirely from AnalysisContext — data comes from:
 *     uploaded traffic → pipeline → model inference → API → context
 *   Shows: devices monitored, entity selector, affected device detail,
 *   attack trajectory, WHY (explainability), MITRE mapping,
 *   recommended action.  Nothing is hard-coded.
 *
 * FALLBACK MODE (no analysis loaded):
 *   Shows an upload prompt and the legacy sample-based demo view
 *   (sample #N from the pre-built test set) so developers can still
 *   explore the model without uploading a file.
 *
 * Requirements 31–33 compliance:
 *   - Primary concept is the monitored network / device, not "Sample #N".
 *   - No device IDs, probabilities, counts, or stages are hard-coded.
 *   - When no IP identifiers exist in the upload the view is labelled
 *     "NETWORK-LEVEL PREDICTION" — no device identity is manufactured.
 *   - Everything originates from uploaded telemetry → API → this page.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  Shield, AlertTriangle, CheckCircle,
  TrendingUp, Info, UploadCloud, ChevronRight,
  Monitor, Zap, Eye,
} from 'lucide-react'

import { useAnalysisContext }  from '../context/AnalysisContext'
import { useSampleContext }    from '../context/SampleContext'
import { useApi }              from '../hooks/useApi'
import { getPrediction, getForecast } from '../services/api'

import Panel       from '../components/Panel'
import StageBadge  from '../components/StageBadge'
import MitreBadge  from '../components/MitreBadge'
import RiskIndicator from '../components/RiskIndicator'
import AlertCard   from '../components/AlertCard'
import LoadingSkeleton, { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState  from '../components/ErrorState'
import MetricCard  from '../components/MetricCard'
import {
  STAGE_COLORS, STAGE_ICONS,
  fmtPct, fmtPctShort, type AttackStageKey,
} from '../utils/constants'
import type { EntityRecord, EntityTrajectoryStep, NetworkPrediction } from '../types/api'

// ─────────────────────────────────────────────────────────────────────────────
// Small reusable sub-components
// ─────────────────────────────────────────────────────────────────────────────

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ color: '#3d5275', fontSize: '0.75rem' }}>{label}</span>
      {children}
    </div>
  )
}

function RiskBadge({ risk }: { risk: string }) {
  const color =
    risk === 'CRITICAL' ? '#7c3aed'
    : risk === 'HIGH'   ? '#ef4444'
    : risk === 'MEDIUM' ? '#f59e0b'
    : '#22c55e'
  return (
    <span style={{
      background: `${color}18`, border: `1px solid ${color}55`,
      borderRadius: 4, padding: '2px 8px',
      color, fontSize: '0.7rem', fontWeight: 700,
    }}>
      {risk}
    </span>
  )
}

/** Risk colour for a numeric probability. */
function probColor(p: number) {
  if (p >= 0.7) return '#ef4444'
  if (p >= 0.3) return '#f59e0b'
  return '#22c55e'
}

// ─────────────────────────────────────────────────────────────────────────────
// Stage-specific recommended actions
// ─────────────────────────────────────────────────────────────────────────────

const STAGE_ACTIONS: Record<string, string> = {
  Benign:
    'No immediate action required. Continue routine monitoring and ensure ' +
    'baseline alerting thresholds are correctly configured.',
  Reconnaissance:
    'Tighten firewall ingress rules. Enable port-scan detection and rate-limit ' +
    'ICMP/TCP-SYN traffic from unfamiliar source IPs. Review exposed services.',
  BruteForce:
    'Enforce account lockout policies. Enable multi-factor authentication on ' +
    'all externally reachable services. Block offending IPs at the perimeter ' +
    'and rotate any credentials that may have been compromised.',
  LateralMovement:
    'Segment internal network traffic immediately. Audit active sessions and ' +
    'revoke unused service accounts. Deploy endpoint detection on internal hosts ' +
    'and inspect east–west traffic for anomalous RPC/SMB activity.',
  CommandAndControl:
    'Isolate affected hosts from the network. Capture and analyse C2 traffic ' +
    'for indicators of compromise. Initiate incident-response procedures, ' +
    'preserve forensic evidence, and notify your security operations team.',
}

function getRecommendedAction(stage: string): string {
  return STAGE_ACTIONS[stage] ?? 'Review network traffic and apply appropriate defensive measures.'
}

// ─────────────────────────────────────────────────────────────────────────────
// Entity list / selector
// ─────────────────────────────────────────────────────────────────────────────

interface EntityListProps {
  entities:         EntityRecord[]
  selectedId:       string | null
  onSelect:         (id: string) => void
  normalCount:      number
  suspiciousCount:  number
  highRiskCount:    number
  totalCount:       number
}

function EntityList({
  entities, selectedId, onSelect,
  normalCount, suspiciousCount, highRiskCount, totalCount,
}: EntityListProps) {
  const [search, setSearch] = useState('')
  const filtered = useMemo(() =>
    search.trim()
      ? entities.filter(e => e.entity_id.includes(search.trim()))
      : entities,
  [entities, search])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Summary counts */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
      }}>
        {[
          { label: 'Monitored',  value: totalCount,      color: '#c8d8ec' },
          { label: 'Normal',     value: normalCount,     color: '#22c55e' },
          { label: 'Suspicious', value: suspiciousCount, color: '#f59e0b' },
          { label: 'High Risk',  value: highRiskCount,   color: '#ef4444' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: '#070d1a', border: `1px solid ${color}22`,
            borderRadius: 6, padding: '8px 10px', textAlign: 'center',
          }}>
            <div style={{ color, fontSize: '1.25rem', fontWeight: 800, lineHeight: 1.1 }}>
              {value}
            </div>
            <div style={{ color: '#3d5275', fontSize: '0.62rem', marginTop: 2 }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      {entities.length > 5 && (
        <input
          type="text"
          placeholder="Filter by IP…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%', padding: '6px 10px', boxSizing: 'border-box',
            background: '#0a1425', border: '1px solid #1a2c4a',
            borderRadius: 5, color: '#c8d8ec', fontSize: '0.78rem', outline: 'none',
          }}
        />
      )}

      {/* Entity rows */}
      <div style={{
        maxHeight: 280, overflowY: 'auto',
        display: 'flex', flexDirection: 'column', gap: 4,
      }}>
        {filtered.length === 0 && (
          <div style={{ color: '#2a4060', fontSize: '0.75rem', padding: '8px 0' }}>
            No matching entities.
          </div>
        )}
        {filtered.map(ent => {
          const isSelected = ent.entity_id === selectedId
          const c = probColor(ent.attack_probability)
          return (
            <button
              key={ent.entity_id}
              onClick={() => onSelect(ent.entity_id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px',
                background: isSelected ? '#0f1d33' : '#070d1a',
                border: `1px solid ${isSelected ? '#3b82f6' : '#1a2c4a'}`,
                borderLeft: `3px solid ${isSelected ? '#3b82f6' : c}`,
                borderRadius: 6, cursor: 'pointer',
                textAlign: 'left', width: '100%',
              }}
            >
              <Monitor size={13} color={c} style={{ flexShrink: 0 }} />
              <span style={{
                color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.78rem',
                fontWeight: isSelected ? 700 : 400, flex: 1,
              }}>
                {ent.entity_id}
              </span>
              <span style={{ color: '#3d5275', fontSize: '0.65rem', flexShrink: 0 }}>
                {ent.record_count.toLocaleString()} pkts
              </span>
              <RiskBadge risk={ent.risk} />
            </button>
          )
        })}
      </div>

      <div style={{ color: '#1e3a5f', fontSize: '0.62rem', marginTop: 2 }}>
        Risk / stage values are network-level predictions applied to all monitored devices.
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Trajectory timeline
// ─────────────────────────────────────────────────────────────────────────────

function TrajectoryTimeline({ trajectory }: { trajectory: EntityTrajectoryStep[] }) {
  const chartData = trajectory.map(t => ({
    name:  `+${t.step * 10}s`,
    prob:  t.attack_probability,
    stage: t.stage,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Step-by-step progression */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, flexWrap: 'wrap' }}>
        {trajectory.map((t, i) => {
          const c = STAGE_COLORS[t.stage as AttackStageKey] ?? '#7d95b5'
          const icon = STAGE_ICONS[t.stage as AttackStageKey] ?? '⚡'
          return (
            <div key={t.step} style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                padding: '8px 12px',
                background: `${c}10`, border: `1px solid ${c}33`,
                borderRadius: 7, minWidth: 90,
              }}>
                <span style={{ fontSize: '1rem' }}>{icon}</span>
                <span style={{ color: c, fontSize: '0.7rem', fontWeight: 700 }}>{t.stage}</span>
                <span style={{ color: c, fontSize: '0.85rem', fontWeight: 800 }}>
                  {fmtPctShort(t.attack_probability)}
                </span>
                <span style={{ color: '#2a4060', fontSize: '0.6rem' }}>
                  +{t.step * 10}s
                </span>
              </div>
              {i < trajectory.length - 1 && (
                <ChevronRight size={16} color="#1e3a5f" style={{ margin: '0 2px' }} />
              )}
            </div>
          )
        })}
      </div>

      {/* Area chart */}
      <ResponsiveContainer width="100%" height={160}>
        <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id="trajGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
          <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 10 }} />
          <YAxis
            domain={[0, 1]} tickFormatter={v => `${((v as number) * 100).toFixed(0)}%`}
            tick={{ fill: '#3d5275', fontSize: 10 }}
          />
          <Tooltip
            contentStyle={{
              background: '#0d1526', border: '1px solid #1a2c4a',
              borderRadius: 6, fontSize: '0.78rem',
            }}
            formatter={(v: unknown, _: unknown, props: { payload?: { stage?: string } }) => [
              fmtPct(typeof v === 'number' ? v : 0),
              props.payload?.stage ?? 'Attack Probability',
            ]}
          />
          <Area
            type="monotone" dataKey="prob" stroke="#ef4444" strokeWidth={2}
            fill="url(#trajGrad)"
            dot={{ fill: '#ef4444', r: 4, strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Device detail panel — shown when an entity or network-level view is active
// ─────────────────────────────────────────────────────────────────────────────

interface DeviceDetailProps {
  label:       string          // device IP or "Network-Level"
  isNetwork:   boolean         // true → no real device ID
  prediction:  NetworkPrediction | EntityRecord
  explainability: Array<{ feature: string; sensitivity: number }>
}

function DeviceDetail({ label, isNetwork, prediction, explainability }: DeviceDetailProps) {
  const stageColor = STAGE_COLORS[prediction.predicted_stage as AttackStageKey] ?? '#7d95b5'
  const action     = getRecommendedAction(prediction.predicted_stage)
  const topFeats   = explainability.slice(0, 5)
  const maxSens    = topFeats[0]?.sensitivity ?? 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Device / scope header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px',
        background: isNetwork
          ? 'rgba(59,130,246,0.06)' : `${stageColor}08`,
        border: `1px solid ${isNetwork ? 'rgba(59,130,246,0.2)' : `${stageColor}33`}`,
        borderRadius: 7,
      }}>
        {isNetwork
          ? <Shield size={18} color="#3b82f6" />
          : <Monitor size={18} color={stageColor} />
        }
        <div style={{ flex: 1 }}>
          <div style={{
            color: isNetwork ? '#93c5fd' : '#c8d8ec',
            fontFamily: 'monospace', fontSize: '0.92rem', fontWeight: 700,
          }}>
            {isNetwork ? 'NETWORK-LEVEL PREDICTION' : label}
          </div>
          {isNetwork && (
            <div style={{ color: '#2a5070', fontSize: '0.68rem', marginTop: 2 }}>
              No device/IP identifiers found in uploaded file — prediction applies to the entire network capture
            </div>
          )}
          {/* When a specific device is selected the prediction is still
              network-level — the model has no per-entity inference capability.
              Make this explicit directly in the device header. */}
          {!isNetwork && (
            <div style={{ color: '#2a5070', fontSize: '0.68rem', marginTop: 2 }}>
              Prediction scope: <strong style={{ color: '#60a5fa' }}>network-level</strong>
              {' '}— values reflect the entire capture, not this device individually
            </div>
          )}
        </div>
        <RiskBadge risk={prediction.risk} />
      </div>

      {/* Key metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
        <div style={{
          background: '#070d1a', border: `1px solid ${stageColor}33`,
          borderRadius: 7, padding: '10px 14px',
        }}>
          <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
            Attack Probability
          </div>
          <div style={{
            color: probColor(prediction.attack_probability),
            fontSize: '1.4rem', fontWeight: 800, marginTop: 4,
          }}>
            {fmtPct(prediction.attack_probability)}
          </div>
        </div>
        <div style={{
          background: '#070d1a', border: `1px solid ${stageColor}33`,
          borderRadius: 7, padding: '10px 14px',
        }}>
          <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
            Current Stage
          </div>
          <div style={{ marginTop: 6 }}>
            <StageBadge stage={prediction.predicted_stage} size="md" />
          </div>
        </div>
        <div style={{
          background: '#070d1a', border: `1px solid ${stageColor}33`,
          borderRadius: 7, padding: '10px 14px',
        }}>
          <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
            Stage Confidence
          </div>
          <div style={{
            color: '#7d95b5', fontSize: '1.1rem', fontWeight: 700, marginTop: 4,
          }}>
            {fmtPct(prediction.stage_confidence)}
          </div>
        </div>
      </div>

      {/* Trajectory */}
      <Panel
        title="Future Attack Trajectory"
        subtitle="5-step autoregressive forecast — no ground truth used"
      >
        <TrajectoryTimeline trajectory={prediction.trajectory} />
      </Panel>

      {/* WHY — top features */}
      {topFeats.length > 0 && (
        <Panel
          title="WHY? — Top Evidence Features"
          subtitle="Feature ablation sensitivity — prediction influence, not causal attribution"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
            {topFeats.map((f, i) => {
              const rel = f.sensitivity / maxSens
              const featColors = ['#ef4444','#f97316','#f59e0b','#eab308','#84cc16']
              const c = featColors[i] ?? '#7d95b5'
              return (
                <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ color: '#1e3a5f', fontSize: '0.65rem', width: 16, textAlign: 'right', flexShrink: 0 }}>
                    #{i + 1}
                  </span>
                  <span style={{
                    color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem',
                    width: 220, flexShrink: 0,
                  }}>
                    {f.feature}
                  </span>
                  <div style={{
                    flex: 1, height: 6, background: '#111e35',
                    borderRadius: 3, overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', width: `${rel * 100}%`,
                      background: c, borderRadius: 3,
                    }} />
                  </div>
                  <span style={{
                    color: c, fontSize: '0.7rem',
                    fontFamily: 'monospace', width: 62, textAlign: 'right', flexShrink: 0,
                  }}>
                    {f.sensitivity.toFixed(5)}
                  </span>
                </div>
              )
            })}
          </div>
        </Panel>
      )}

      {/* MITRE ATT&CK */}
      {prediction.mitre_attack_id && (
        <Panel title="MITRE ATT&CK">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <MitreBadge
              id={prediction.mitre_attack_id}
              name={prediction.mitre_attack_name ?? ''}
            />
            <div style={{ color: '#1e3a5f', fontSize: '0.65rem' }}>
              Representative stage-to-technique mapping — prototype assignment,
              not direct ATT&CK technique detection.
            </div>
          </div>
        </Panel>
      )}

      {/* Recommended action */}
      <Panel title="Recommended Action">
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          padding: '10px 14px',
          background: prediction.predicted_stage === 'Benign'
            ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${prediction.predicted_stage === 'Benign'
            ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
          borderRadius: 7,
        }}>
          <AlertTriangle
            size={16}
            color={prediction.predicted_stage === 'Benign' ? '#22c55e' : '#ef4444'}
            style={{ marginTop: 1, flexShrink: 0 }}
          />
          <div style={{ color: '#c8d8ec', fontSize: '0.82rem', lineHeight: 1.6 }}>
            {action}
          </div>
        </div>
      </Panel>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Upload prompt (shown when no analysis loaded)
// ─────────────────────────────────────────────────────────────────────────────

function UploadPrompt() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 16,
      padding: '48px 24px',
      background: '#0b1526', border: '1px dashed #1a2c4a',
      borderRadius: 12, textAlign: 'center',
    }}>
      <UploadCloud size={48} color="#1e3a5f" />
      <div>
        <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>
          No Analysis Loaded
        </div>
        <div style={{ color: '#3d5275', fontSize: '0.82rem', maxWidth: 420 }}>
          Upload your network telemetry to see device-level attack forecasting.
          Devices, risk levels, and predictions will appear here automatically.
        </div>
      </div>
      <Link
        to="/upload"
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 22px',
          background: '#1d4ed8', border: 'none',
          borderRadius: 7, color: '#fff',
          fontSize: '0.85rem', fontWeight: 600,
          textDecoration: 'none',
        }}
      >
        <UploadCloud size={15} /> Upload Telemetry File
      </Link>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Legacy demo view (sample-based, shown as secondary when no upload)
// ─────────────────────────────────────────────────────────────────────────────

function LegacyDemoView() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps     = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const pred     = useApi(() => getPrediction(sampleId), deps)
  const forecast = useApi(() => getForecast(sampleId),   deps)

  const chartData = useMemo(() => {
    if (!forecast.data) return []
    return forecast.data.forecast.map(f => ({
      name: `Step ${f.step}`,
      prob: f.attack_probability,
    }))
  }, [forecast.data])

  const loading = pred.loading || forecast.loading
  const error   = pred.error || forecast.error

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 14px',
        background: 'rgba(59,130,246,0.06)',
        border: '1px solid rgba(59,130,246,0.18)',
        borderRadius: 6,
      }}>
        <Info size={13} color="#3b82f6" />
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
          <strong style={{ color: '#93c5fd' }}>Developer / Demo mode</strong>
          {' '}— pre-built test set, Sample #{sampleId}.
          Upload telemetry above to see device-level analysis.
        </span>
      </div>

      {error && !loading && <ErrorState error={error} onRetry={pred.refetch} />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        {loading
          ? Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
          : pred.data && <>
            <MetricCard
              label="Attack Probability"
              value={fmtPct(pred.data.attack_probability)}
              sub={pred.data.attack_detected ? '⚠ Attack Detected' : '✓ No Attack'}
              accentColor={probColor(pred.data.attack_probability)}
              icon={<Zap size={16} />}
            />
            <MetricCard
              label="Predicted Stage"
              value={<StageBadge stage={pred.data.predicted_stage} size="lg" />}
              sub="Model prediction"
              accentColor={STAGE_COLORS[pred.data.predicted_stage as AttackStageKey] ?? '#3b82f6'}
              icon={<Eye size={16} />}
            />
            <MetricCard
              label="Stage Confidence"
              value={fmtPct(pred.data.stage_confidence)}
              sub="Prediction confidence"
              accentColor="#06b6d4"
              icon={<Shield size={16} />}
            />
            <MetricCard
              label="Forecast Horizon"
              value={forecast.data ? `${forecast.data.horizon} Steps` : '5 Steps'}
              sub="Autoregressive forecast"
              accentColor="#8b5cf6"
              icon={<TrendingUp size={16} />}
            />
          </>
        }
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>
        <Panel title="Attack Risk Forecast" subtitle="5-step autoregressive — no ground truth used">
          {forecast.loading
            ? <LoadingSkeleton lines={5} height={200} />
            : forecast.data && (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
                  <defs>
                    <linearGradient id="demoRiskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
                  <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
                  <YAxis
                    domain={[0, 1]}
                    tickFormatter={v => `${((v as number) * 100).toFixed(0)}%`}
                    tick={{ fill: '#3d5275', fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
                    formatter={(v: unknown) => [fmtPct(typeof v === 'number' ? v : 0), 'Attack Probability']}
                  />
                  <Area type="monotone" dataKey="prob" stroke="#ef4444" strokeWidth={2}
                    fill="url(#demoRiskGrad)" dot={{ fill: '#ef4444', r: 4 }} />
                </AreaChart>
              </ResponsiveContainer>
            )
          }
        </Panel>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Panel title="Overall Risk">
            {pred.loading
              ? <LoadingSkeleton lines={3} height={80} />
              : pred.data && <RiskIndicator probability={pred.data.attack_probability} size="lg" />
            }
          </Panel>
          <Panel title="Prediction Detail">
            {pred.loading
              ? <LoadingSkeleton lines={4} height={100} />
              : pred.data && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <Row label="Predicted Stage">
                    <StageBadge stage={pred.data.predicted_stage} />
                  </Row>
                  <Row label="Reference Stage">
                    <span style={{ color: '#5d7a9a', fontSize: '0.78rem' }}>
                      {pred.data.current_true_stage}
                      <span style={{ color: '#1e3a5f', marginLeft: 4 }}>(ground truth)</span>
                    </span>
                  </Row>
                  <Row label="ATT&CK Mapping">
                    <MitreBadge id={pred.data.mitre_attack_id} name={pred.data.mitre_attack_name} size="sm" />
                  </Row>
                </div>
              )
            }
          </Panel>
        </div>
      </div>

      {pred.data?.attack_detected && (
        <AlertCard
          attackProbability={pred.data.attack_probability}
          predictedStage={pred.data.predicted_stage}
          mitreId={pred.data.mitre_attack_id}
          mitreName={pred.data.mitre_attack_name}
          sampleId={sampleId}
        />
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Primary entity-centric view
// ─────────────────────────────────────────────────────────────────────────────

function EntityDashboard() {
  const {
    analysis, entitiesData,
    selectedEntityId, selectedEntity,
    selectEntity,
  } = useAnalysisContext()

  // Derive the active prediction: selected entity or network-level fallback
  const activePrediction: NetworkPrediction | EntityRecord | null =
    selectedEntity ?? entitiesData?.network_prediction ?? null

  const explainability = analysis?.explainability ?? []
  const hasEntities    = entitiesData?.has_entity_ids ?? false
  const entities       = entitiesData?.entities ?? []
  const netPred        = entitiesData?.network_prediction

  // Header stats from the analysis input
  const totalEntities  = entitiesData?.total_entities ?? 0
  const normalCount    = entitiesData?.normal_count    ?? 0
  const suspCount      = entitiesData?.suspicious_count ?? 0
  const highCount      = entitiesData?.high_risk_count  ?? 0

  // Timestamp range
  const tsStart = analysis?.input.ts_start ?? ''
  const tsEnd   = analysis?.input.ts_end   ?? ''
  const filename = analysis?.input.filename ?? ''

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Analysis source banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '8px 14px',
        background: 'rgba(34,197,94,0.06)',
        border: '1px solid rgba(34,197,94,0.2)',
        borderRadius: 7,
        flexWrap: 'wrap',
      }}>
        <CheckCircle size={14} color="#22c55e" style={{ flexShrink: 0 }} />
        <span style={{ color: '#4ade80', fontSize: '0.78rem', fontWeight: 600 }}>
          Live Analysis
        </span>
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{
          color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem',
        }}>
          {filename}
        </span>
        {tsStart && (
          <>
            <span style={{ color: '#1e3a5f' }}>·</span>
            <span style={{ color: '#2a4060', fontSize: '0.72rem' }}>
              {tsStart} → {tsEnd}
            </span>
          </>
        )}
        <div style={{ flex: 1 }} />
        <Link to="/upload" style={{
          color: '#3d5275', fontSize: '0.7rem', textDecoration: 'none',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          <UploadCloud size={11} /> Upload new file
        </Link>
      </div>

      {/* No IP scope notice */}
      {!hasEntities && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '10px 14px',
          background: 'rgba(59,130,246,0.06)',
          border: '1px solid rgba(59,130,246,0.18)',
          borderRadius: 7,
        }}>
          <Info size={14} color="#3b82f6" style={{ marginTop: 1, flexShrink: 0 }} />
          <div style={{ color: '#5d7a9a', fontSize: '0.78rem' }}>
            <strong style={{ color: '#93c5fd' }}>NETWORK-LEVEL PREDICTION</strong>
            {' '}— the uploaded file does not contain source/destination IP or host
            identifiers. The prediction applies to the entire network capture.
            No individual device identity has been inferred or manufactured.
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: hasEntities ? '280px 1fr' : '1fr', gap: 16 }}>

        {/* Left: entity list (only when IPs present) */}
        {hasEntities && entities.length > 0 && (
          <Panel
            title="Monitored Devices"
            subtitle={`${totalEntities} endpoint${totalEntities !== 1 ? 's' : ''} from telemetry`}
          >
            <EntityList
              entities={entities}
              selectedId={selectedEntityId}
              onSelect={selectEntity}
              normalCount={normalCount}
              suspiciousCount={suspCount}
              highRiskCount={highCount}
              totalCount={totalEntities}
            />
          </Panel>
        )}

        {/* Right: device / network detail */}
        <div>
          {activePrediction ? (
            <DeviceDetail
              label={selectedEntity?.entity_id ?? 'Network'}
              isNetwork={!selectedEntity || !hasEntities}
              prediction={activePrediction}
              explainability={explainability}
            />
          ) : (
            <Panel title="Select a Device">
              <div style={{ color: '#2a4060', fontSize: '0.82rem', padding: '12px 0' }}>
                Select a device from the list on the left to view its details.
              </div>
            </Panel>
          )}
        </div>
      </div>

      {/* Network-level summary (always shown at bottom when IPs present) */}
      {hasEntities && netPred && (
        <Panel
          title="Network-Level Summary"
          subtitle="Aggregate prediction for the entire traffic capture"
        >
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {[
              { label: 'Attack Probability', value: fmtPct(netPred.attack_probability), color: probColor(netPred.attack_probability) },
              { label: 'Risk Level',         value: netPred.risk,               color: probColor(netPred.attack_probability) },
              { label: 'Predicted Stage',    value: netPred.predicted_stage,    color: STAGE_COLORS[netPred.predicted_stage as AttackStageKey] ?? '#7d95b5' },
              { label: 'Stage Confidence',   value: fmtPct(netPred.stage_confidence), color: '#7d95b5' },
              { label: 'Highest Risk',       value: netPred.highest_risk,       color: probColor(netPred.attack_probability) },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                background: '#070d1a', border: '1px solid #1a2c4a',
                borderRadius: 6, padding: '8px 10px',
              }}>
                <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
                  {label}
                </div>
                <div style={{ color, fontSize: '0.9rem', fontWeight: 700, marginTop: 4 }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
          <div style={{ color: '#1e3a5f', fontSize: '0.65rem', marginTop: 8 }}>
            Prediction scope: network-level. The model was trained on aggregated network
            states — per-entity model predictions are not available.
          </div>
        </Panel>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root Dashboard component
// ─────────────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { hasAnalysis, analysisLabel, isRestoring, restoreStatus } = useAnalysisContext()

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>
          Network Security Status
        </h1>
        {hasAnalysis && (
          <span style={{ color: '#2a4060', fontSize: '0.78rem', fontFamily: 'monospace' }}>
            — {analysisLabel}
          </span>
        )}
      </div>

      {/* Restoring — show skeleton so there is no flash of the demo view */}
      {isRestoring && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <LoadingSkeleton lines={3} height={80} />
          <LoadingSkeleton lines={6} height={200} />
          <div style={{ color: '#2a4060', fontSize: '0.75rem', textAlign: 'center' }}>
            Restoring previous analysis…
          </div>
        </div>
      )}

      {/* Expired — analysis_id was stored but backend no longer has it */}
      {!isRestoring && restoreStatus === 'expired' && (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14,
          padding: '36px 24px',
          background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.25)',
          borderRadius: 12, textAlign: 'center',
        }}>
          <AlertTriangle size={40} color="#f59e0b" />
          <div>
            <div style={{ color: '#f59e0b', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>
              Previous Analysis Unavailable
            </div>
            <div style={{ color: '#927a5a', fontSize: '0.82rem', maxWidth: 420 }}>
              The backend was restarted and the previous analysis is no longer in memory.
              Upload your telemetry again to restore the analysis.
            </div>
          </div>
          <Link to="/upload" style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '10px 22px', background: '#1d4ed8',
            borderRadius: 7, color: '#fff',
            fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none',
          }}>
            <UploadCloud size={15} /> Upload New Telemetry
          </Link>
        </div>
      )}

      {/* Main content — only when restore is complete */}
      {!isRestoring && restoreStatus !== 'expired' && (
        hasAnalysis
          ? <EntityDashboard />
          : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <UploadPrompt />
              <Panel
                title="Developer / Demo View"
                subtitle="Pre-built test set — sample-based preview. Not the primary product view."
              >
                <LegacyDemoView />
              </Panel>
            </div>
          )
      )}
    </div>
  )
}
