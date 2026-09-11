/**
 * AttackForecast.tsx — 5-step autoregressive forecast page.
 *
 * PRIMARY MODE  (uploaded analysis present in AnalysisContext):
 *   Data source: analysis.forecast from AnalysisContext — no additional API call.
 *   Prediction scope is always NETWORK-LEVEL; labelled accordingly.
 *   When a new file is uploaded the context is replaced and this page
 *   automatically reflects the new analysis.
 *
 * FALLBACK MODE (no analysis loaded):
 *   Upload prompt + collapsible Developer/Demo section backed by
 *   GET /forecast/{sample_id} from SampleContext.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts'
import { Info, ChevronRight, UploadCloud, ChevronDown } from 'lucide-react'

import { useAnalysisContext } from '../context/AnalysisContext'
import { useSampleContext }   from '../context/SampleContext'
import { useApi }             from '../hooks/useApi'
import { getForecast }        from '../services/api'

import Panel          from '../components/Panel'
import StageBadge     from '../components/StageBadge'
import MitreBadge     from '../components/MitreBadge'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState     from '../components/ErrorState'
import { STAGE_COLORS, fmtPct, type AttackStageKey } from '../utils/constants'
import type { UploadForecastStep } from '../types/api'

// ─────────────────────────────────────────────────────────────────────────────
// Shared step card (works for both UploadForecastStep and ForecastStep shapes)
// ─────────────────────────────────────────────────────────────────────────────

interface StepCardProps {
  step:             number
  stage:            string
  attackProb:       number
  stageConf:        number
  mitreId:          string | null | undefined
  mitreName:        string | null | undefined
  isFirst:          boolean
}

function StepCard({ step, stage, attackProb, stageConf, mitreId, mitreName, isFirst }: StepCardProps) {
  const c = STAGE_COLORS[stage as AttackStageKey] ?? '#7d95b5'
  return (
    <div style={{
      background: '#070d1a', border: `1px solid ${c}33`, borderRadius: 9,
      padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10,
      boxShadow: isFirst ? `0 0 18px ${c}18` : 'none',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: c, fontSize: '0.65rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          STEP {step}
        </span>
        <span style={{ color: attackProb >= 0.5 ? '#ef4444' : '#22c55e', fontSize: '0.65rem', fontWeight: 700 }}>
          {attackProb >= 0.5 ? '⚠ ATTACK' : '✓ BENIGN'}
        </span>
      </div>
      <StageBadge stage={stage} size="md" />
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ color: '#3d5275', fontSize: '0.68rem' }}>Attack Prob.</span>
          <span style={{ color: c, fontSize: '0.8rem', fontWeight: 700 }}>{fmtPct(attackProb)}</span>
        </div>
        <div style={{ height: 5, background: '#0f1d33', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${attackProb * 100}%`, background: `linear-gradient(90deg,${c}88,${c})`, borderRadius: 3 }} />
        </div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ color: '#3d5275', fontSize: '0.68rem' }}>Stage Confidence</span>
        <span style={{ color: '#7d95b5', fontSize: '0.75rem', fontWeight: 600 }}>{fmtPct(stageConf)}</span>
      </div>
      <MitreBadge id={mitreId ?? ''} name={mitreName ?? ''} size="sm" />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Primary view — driven by AnalysisContext
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisForecastView() {
  const { analysis, analysisId, selectedEntity, entitiesData } = useAnalysisContext()

  // Forecast comes directly from the stored analysis — no extra fetch needed.
  const forecast: UploadForecastStep[] = analysis?.forecast ?? []
  const currentState = analysis?.current_state
  const filename     = analysis?.input.filename ?? ''
  const tsStart      = analysis?.input.ts_start  ?? ''
  const hasEntityIds = entitiesData?.has_entity_ids ?? false

  const chartData = forecast.map(f => ({
    name:        `+${f.step * 10}s`,
    probability: f.attack_probability,
    confidence:  f.stage_confidence,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Source banner */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
        padding: '8px 14px',
        background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)',
        borderRadius: 7,
      }}>
        <span style={{ color: '#4ade80', fontSize: '0.78rem', fontWeight: 600 }}>Live Analysis</span>
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem' }}>{filename}</span>
        {tsStart && <><span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#2a4060', fontSize: '0.72rem' }}>from {tsStart}</span></>}
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#2a4060', fontSize: '0.68rem', fontFamily: 'monospace' }}>id: {analysisId}</span>
      </div>

      {/* Prediction scope notice */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '10px 14px',
        background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)',
        borderRadius: 7,
      }}>
        <Info size={14} color="#3b82f6" style={{ marginTop: 1, flexShrink: 0 }} />
        <div style={{ color: '#5d7a9a', fontSize: '0.78rem' }}>
          <strong style={{ color: '#93c5fd' }}>NETWORK-LEVEL PREDICTION</strong>
          {' '}— the Temporal Transformer was trained on aggregated network states.
          {selectedEntity && hasEntityIds
            ? ` Observed endpoint: ${selectedEntity.entity_id}. Prediction reflects the aggregate network, not this device individually.`
            : ' Prediction reflects the aggregate network capture.'}
          {' '}Ground truth not used — genuine autoregressive forecast.
        </div>
      </div>

      {/* Current state strip */}
      {currentState && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10,
        }}>
          {[
            { label: 'Current Stage',    value: <StageBadge stage={currentState.stage} size="sm" /> },
            { label: 'Attack Prob.',     value: <span style={{ color: currentState.attack_probability >= 0.5 ? '#ef4444' : '#22c55e', fontWeight: 700 }}>{fmtPct(currentState.attack_probability)}</span> },
            { label: 'Stage Confidence', value: <span style={{ color: '#7d95b5', fontWeight: 600 }}>{fmtPct(currentState.stage_confidence)}</span> },
            { label: 'Risk',             value: <span style={{ color: currentState.risk === 'HIGH' || currentState.risk === 'CRITICAL' ? '#ef4444' : currentState.risk === 'MEDIUM' ? '#f59e0b' : '#22c55e', fontWeight: 700 }}>{currentState.risk}</span> },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
              <div>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Step cards */}
      <Panel title="5-Step Prediction Timeline" subtitle="Autoregressive — each predicted state fed back as next input">
        {forecast.length === 0
          ? <div style={{ color: '#2a4060', fontSize: '0.82rem' }}>No forecast data in analysis.</div>
          : (
            <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
              {forecast.map((f, i) => (
                <div key={f.step} style={{ flex: 1, display: 'flex', alignItems: 'stretch', gap: 8 }}>
                  <StepCard
                    step={f.step} stage={f.stage}
                    attackProb={f.attack_probability} stageConf={f.stage_confidence}
                    mitreId={f.mitre_attack_id} mitreName={f.mitre_attack_name}
                    isFirst={i === 0}
                  />
                  {i < forecast.length - 1 && (
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <ChevronRight size={16} color="#1e3a5f" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        }
      </Panel>

      {/* Chart */}
      {forecast.length > 0 && (
        <Panel title="Forecast Probability Chart" subtitle="Attack probability and stage confidence across the 5-step horizon">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
              <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
              <YAxis domain={[0, 1]} tickFormatter={v => `${((v as number) * 100).toFixed(0)}%`} tick={{ fill: '#3d5275', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
                formatter={(v: unknown, name: unknown) => [fmtPct(typeof v === 'number' ? v : 0), name === 'probability' ? 'Attack Probability' : 'Stage Confidence'] as [string, string]}
              />
              <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#5d7a9a' }} />
              <ReferenceLine y={0.5} stroke="#f59e0b88" strokeDasharray="4 3" label={{ value: '50%', fill: '#f59e0b', fontSize: 10 }} />
              <ReferenceLine y={0.7} stroke="#ef444444" strokeDasharray="3 3" />
              <Line type="monotone" dataKey="probability" name="Attack Probability" stroke="#ef4444" strokeWidth={2} dot={{ fill: '#ef4444', r: 4, strokeWidth: 0 }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="confidence"  name="Stage Confidence"  stroke="#06b6d4" strokeWidth={2} strokeDasharray="5 3" dot={{ fill: '#06b6d4', r: 4, strokeWidth: 0 }} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      )}

      {/* Detail table */}
      {forecast.length > 0 && (
        <Panel title="Step-by-Step Detail">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  {['Step', 'Time', 'Stage', 'Attack Prob.', 'Stage Conf.', 'Risk', 'MITRE ID', 'Technique'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 10px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid #1a2c4a' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {forecast.map((f, i) => {
                  const c = STAGE_COLORS[f.stage as AttackStageKey] ?? '#7d95b5'
                  return (
                    <tr key={f.step} style={{ background: i % 2 === 0 ? 'transparent' : '#070d1a' }}>
                      <td style={{ padding: '8px 10px', color: '#5d7a9a', fontFamily: 'monospace' }}>{f.step}</td>
                      <td style={{ padding: '8px 10px', color: '#2a4060', fontFamily: 'monospace', fontSize: '0.72rem' }}>+{f.step * 10}s</td>
                      <td style={{ padding: '8px 10px' }}><StageBadge stage={f.stage} size="sm" /></td>
                      <td style={{ padding: '8px 10px', color: c, fontWeight: 700 }}>{fmtPct(f.attack_probability)}</td>
                      <td style={{ padding: '8px 10px', color: '#7d95b5' }}>{fmtPct(f.stage_confidence)}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ color: f.risk === 'HIGH' || f.risk === 'CRITICAL' ? '#ef4444' : f.risk === 'MEDIUM' ? '#f59e0b' : '#22c55e', fontWeight: 700, fontSize: '0.72rem' }}>{f.risk}</span>
                      </td>
                      <td style={{ padding: '8px 10px', color: '#60a5fa', fontFamily: 'monospace' }}>{f.mitre_attack_id ?? '—'}</td>
                      <td style={{ padding: '8px 10px', color: '#5d7a9a' }}>{f.mitre_attack_name ?? 'N/A'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 8, color: '#1e3a5f', fontSize: '0.65rem' }}>
            Prediction scope: network-level. MITRE mappings are prototype stage-to-technique assignments.
          </div>
        </Panel>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Dev/demo fallback — original sample-based view
// ─────────────────────────────────────────────────────────────────────────────

function DemoForecastView() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps     = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const forecast = useApi(() => getForecast(sampleId), deps)

  const chartData = useMemo(() => {
    if (!forecast.data) return []
    return forecast.data.forecast.map(f => ({
      name:        `Step ${f.step}`,
      probability: f.attack_probability,
      confidence:  f.stage_confidence,
    }))
  }, [forecast.data])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6 }}>
        <Info size={13} color="#3b82f6" />
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
          <strong style={{ color: '#93c5fd' }}>Developer / Demo mode</strong> — pre-built test set, Sample #{sampleId}.
        </span>
      </div>

      {forecast.error && !forecast.loading && <ErrorState error={forecast.error} onRetry={forecast.refetch} />}

      {forecast.data && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.18)', borderRadius: 6, fontSize: '0.72rem', color: '#4ade80' }}>
            <Info size={11} />
            Ground truth used: <strong>{forecast.data.ground_truth_used ? 'Yes' : 'No'}</strong>
            {!forecast.data.ground_truth_used && ' — genuine autoregressive forecast'}
          </div>

          <Panel title="5-Step Prediction Timeline">
            <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
              {forecast.data.forecast.map((f, i) => (
                <div key={f.step} style={{ flex: 1, display: 'flex', alignItems: 'stretch', gap: 8 }}>
                  <StepCard
                    step={f.step} stage={f.stage}
                    attackProb={f.attack_probability} stageConf={f.stage_confidence}
                    mitreId={f.mitre_attack_id} mitreName={f.mitre_attack_name}
                    isFirst={i === 0}
                  />
                  {i < forecast.data!.forecast.length - 1 && <div style={{ display: 'flex', alignItems: 'center' }}><ChevronRight size={16} color="#1e3a5f" /></div>}
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Forecast Probability Chart" subtitle="Attack probability and stage confidence">
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
                <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
                <YAxis domain={[0, 1]} tickFormatter={v => `${((v as number) * 100).toFixed(0)}%`} tick={{ fill: '#3d5275', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }} formatter={(v: unknown, name: unknown) => [fmtPct(typeof v === 'number' ? v : 0), name === 'probability' ? 'Attack Probability' : 'Stage Confidence'] as [string, string]} />
                <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#5d7a9a' }} />
                <ReferenceLine y={0.5} stroke="#f59e0b88" strokeDasharray="4 3" />
                <Line type="monotone" dataKey="probability" name="Attack Probability" stroke="#ef4444" strokeWidth={2} dot={{ fill: '#ef4444', r: 4, strokeWidth: 0 }} />
                <Line type="monotone" dataKey="confidence"  name="Stage Confidence"  stroke="#06b6d4" strokeWidth={2} strokeDasharray="5 3" dot={{ fill: '#06b6d4', r: 4, strokeWidth: 0 }} />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
        </>
      )}

      {forecast.loading && <LoadingSkeleton lines={5} height={220} />}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root component
// ─────────────────────────────────────────────────────────────────────────────

export default function AttackForecast() {
  const { hasAnalysis, analysisLabel, isRestoring, restoreStatus } = useAnalysisContext()
  const [demoOpen, setDemoOpen] = useState(false)

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Attack Forecast
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          5-Step Autoregressive Forecast — predicted states fed back into the model at each step
        </p>
      </div>

      {isRestoring && <LoadingSkeleton lines={6} height={220} />}

      {!isRestoring && restoreStatus === 'expired' && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '36px 24px', background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 12, textAlign: 'center' }}>
          <div style={{ color: '#f59e0b', fontSize: '1rem', fontWeight: 700 }}>Previous Analysis Unavailable</div>
          <div style={{ color: '#927a5a', fontSize: '0.82rem' }}>The backend was restarted. Please re-upload your telemetry.</div>
          <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
            <UploadCloud size={14} /> Upload New Telemetry
          </Link>
        </div>
      )}

      {!isRestoring && restoreStatus !== 'expired' && (
        hasAnalysis ? (
          <>
            <div style={{ color: '#2a4060', fontSize: '0.72rem', fontFamily: 'monospace' }}>
              {analysisLabel}
            </div>
            <AnalysisForecastView />
            <div style={{ borderTop: '1px solid #0f1d33', paddingTop: 8 }}>
              <button
                onClick={() => setDemoOpen(o => !o)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', color: '#1e3a5f', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', padding: '4px 0' }}
              >
                <ChevronDown size={12} style={{ transform: demoOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                Developer / Demo View
              </button>
              {demoOpen && <div style={{ marginTop: 10 }}><DemoForecastView /></div>}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: '48px 24px', background: '#0b1526', border: '1px dashed #1a2c4a', borderRadius: 12, textAlign: 'center' }}>
              <UploadCloud size={44} color="#1e3a5f" />
              <div>
                <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>No Analysis Loaded</div>
                <div style={{ color: '#3d5275', fontSize: '0.82rem', maxWidth: 400 }}>Upload network telemetry to run the 5-step autoregressive forecast.</div>
              </div>
              <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
                <UploadCloud size={14} /> Upload Telemetry
              </Link>
            </div>
            <Panel title="Developer / Demo View" subtitle="Pre-built test set — not the primary product view">
              <DemoForecastView />
            </Panel>
          </div>
        )
      )}
    </div>
  )
}
