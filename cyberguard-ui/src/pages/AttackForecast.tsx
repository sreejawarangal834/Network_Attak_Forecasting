/**
 * AttackForecast.tsx — Detailed 5-step autoregressive forecast page.
 *
 * Consumes: GET /forecast/{sample_id}
 * Core World Model capability page — visually centred on the forecast.
 */

import { useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts'
import { Info, ChevronRight } from 'lucide-react'

import { useSampleContext } from '../context/SampleContext'
import { useApi } from '../hooks/useApi'
import { getForecast } from '../services/api'

import Panel from '../components/Panel'
import StageBadge from '../components/StageBadge'
import MitreBadge from '../components/MitreBadge'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'
import { STAGE_COLORS, fmtPct, type AttackStageKey } from '../utils/constants'

function StepCard({ step, isFirst }: {
  step: import('../types/api').ForecastStep
  isFirst: boolean
}) {
  const stageColor = STAGE_COLORS[step.stage as AttackStageKey] ?? '#7d95b5'
  const probPct    = step.attack_probability * 100

  return (
    <div style={{
      background: '#070d1a',
      border: `1px solid ${stageColor}33`,
      borderRadius: 9,
      padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 10,
      position: 'relative',
      boxShadow: isFirst ? `0 0 18px ${stageColor}18` : 'none',
    }}>
      {/* Step label */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span style={{
          color: stageColor, fontSize: '0.65rem', fontWeight: 800,
          textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>
          STEP {step.step}
        </span>
        {step.attack_detected
          ? <span style={{ color: '#ef4444', fontSize: '0.65rem', fontWeight: 700 }}>⚠ ATTACK</span>
          : <span style={{ color: '#22c55e', fontSize: '0.65rem', fontWeight: 700 }}>✓ BENIGN</span>
        }
      </div>

      {/* Stage */}
      <StageBadge stage={step.stage} size="md" />

      {/* Probability bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ color: '#3d5275', fontSize: '0.68rem' }}>Attack Prob.</span>
          <span style={{ color: stageColor, fontSize: '0.8rem', fontWeight: 700 }}>
            {fmtPct(step.attack_probability)}
          </span>
        </div>
        <div style={{ height: 5, background: '#0f1d33', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%', width: `${probPct}%`,
            background: `linear-gradient(90deg, ${stageColor}88, ${stageColor})`,
            borderRadius: 3,
          }} />
        </div>
      </div>

      {/* Confidence */}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ color: '#3d5275', fontSize: '0.68rem' }}>Stage Confidence</span>
        <span style={{ color: '#7d95b5', fontSize: '0.75rem', fontWeight: 600 }}>
          {fmtPct(step.stage_confidence)}
        </span>
      </div>

      {/* MITRE */}
      <MitreBadge id={step.mitre_attack_id} name={step.mitre_attack_name} size="sm" />
    </div>
  )
}

export default function AttackForecast() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps     = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const forecast = useApi(() => getForecast(sampleId), deps)

  const chartData = useMemo(() => {
    if (!forecast.data) return []
    return forecast.data.forecast.map(f => ({
      name:       `Step ${f.step}`,
      probability: f.attack_probability,
      confidence:  f.stage_confidence,
    }))
  }, [forecast.data])

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Page header */}
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Attack Forecast
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          5-Step Autoregressive Forecast — predicted states fed back into the model at each step
        </p>
      </div>

      {/* Error */}
      {forecast.error && !forecast.loading && (
        <ErrorState error={forecast.error} onRetry={forecast.refetch} />
      )}

      {/* Autoregressive note */}
      {forecast.data && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          padding: '10px 14px',
          background: 'rgba(59,130,246,0.06)',
          border: '1px solid rgba(59,130,246,0.18)',
          borderRadius: 7, color: '#5d7a9a', fontSize: '0.78rem',
        }}>
          <Info size={14} style={{ marginTop: 1, flexShrink: 0, color: '#3b82f6' }} />
          <div>
            <strong style={{ color: '#93c5fd' }}>Autoregressive Forecast:</strong>{' '}
            Each predicted network state (S̃<sub>t+k</sub>) is fed back as input for the next step.
            Ground truth used:{' '}
            <strong style={{ color: forecast.data.ground_truth_used ? '#f59e0b' : '#4ade80' }}>
              {forecast.data.ground_truth_used ? 'Yes' : 'No'}
            </strong>
            {!forecast.data.ground_truth_used && ' — this is a genuine future-state simulation.'}
          </div>
        </div>
      )}

      {/* Step cards */}
      <Panel title="5-Step Prediction Timeline">
        {forecast.loading ? (
          <LoadingSkeleton lines={6} height={180} />
        ) : forecast.data ? (
          <div style={{ display: 'flex', alignItems: 'stretch', gap: 8 }}>
            {forecast.data.forecast.map((step, i) => (
              <div key={step.step} style={{ flex: 1, display: 'flex', alignItems: 'stretch', gap: 8 }}>
                <StepCard step={step} isFirst={i === 0} />
                {i < forecast.data!.forecast.length - 1 && (
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <ChevronRight size={16} color="#1e3a5f" />
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : null}
      </Panel>

      {/* Probability + confidence chart */}
      <Panel
        title="Forecast Probability Chart"
        subtitle="Attack probability and stage confidence over the 5-step horizon"
      >
        {forecast.loading ? (
          <LoadingSkeleton lines={5} height={240} />
        ) : forecast.data ? (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
              <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
              <YAxis
                domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: '#3d5275', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
                formatter={(v: unknown, name: unknown) => {
                  const val = typeof v === 'number' ? fmtPct(v) : String(v ?? '')
                  const label = name === 'probability' ? 'Attack Probability' : 'Stage Confidence'
                  return [val, label] as [string, string]
                }}
              />
              <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#5d7a9a' }} />
              <ReferenceLine y={0.5} stroke="#f59e0b88" strokeDasharray="4 3"
                label={{ value: '50%', fill: '#f59e0b', fontSize: 10 }} />
              <ReferenceLine y={0.7} stroke="#ef444444" strokeDasharray="3 3" />
              <Line
                type="monotone" dataKey="probability" name="Attack Probability"
                stroke="#ef4444" strokeWidth={2}
                dot={{ fill: '#ef4444', r: 4, strokeWidth: 0 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone" dataKey="confidence" name="Stage Confidence"
                stroke="#06b6d4" strokeWidth={2} strokeDasharray="5 3"
                dot={{ fill: '#06b6d4', r: 4, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : null}
      </Panel>

      {/* Detailed table */}
      {forecast.data && (
        <Panel title="Step-by-Step Detail">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  {['Step', 'Stage', 'Attack Prob.', 'Stage Conf.', 'Detected', 'MITRE ID', 'Technique'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      color: '#3d5275', fontSize: '0.68rem',
                      textTransform: 'uppercase', letterSpacing: '0.06em',
                      borderBottom: '1px solid #1a2c4a',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {forecast.data.forecast.map((step, i) => {
                  const c = STAGE_COLORS[step.stage as AttackStageKey] ?? '#7d95b5'
                  return (
                    <tr key={step.step} style={{
                      background: i % 2 === 0 ? 'transparent' : '#070d1a',
                    }}>
                      <td style={{ padding: '8px 10px', color: '#5d7a9a', fontFamily: 'monospace' }}>
                        {step.step}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <StageBadge stage={step.stage} size="sm" />
                      </td>
                      <td style={{ padding: '8px 10px', color: c, fontWeight: 700 }}>
                        {fmtPct(step.attack_probability)}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#7d95b5' }}>
                        {fmtPct(step.stage_confidence)}
                      </td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ color: step.attack_detected ? '#ef4444' : '#22c55e', fontWeight: 700 }}>
                          {step.attack_detected ? '⚠ Yes' : '✓ No'}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', color: '#60a5fa', fontFamily: 'monospace' }}>
                        {step.mitre_attack_id || '—'}
                      </td>
                      <td style={{ padding: '8px 10px', color: '#5d7a9a' }}>
                        {step.mitre_attack_name || 'N/A'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 10, color: '#1e3a5f', fontSize: '0.68rem' }}>
            MITRE ATT&CK mappings are representative/prototype stage-to-technique assignments.
            The model predicts network-state attack stages; techniques are inferred from stage labels.
          </div>
        </Panel>
      )}
    </div>
  )
}
