/**
 * Dashboard.tsx — Main SOC overview page.
 *
 * Consumes: GET /predict/{sample_id}, GET /forecast/{sample_id}
 * Shows: attack probability, predicted stage, forecast chart, alert.
 */

import { useMemo } from 'react'
import {
  XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Area, AreaChart,
} from 'recharts'
import { Shield, Zap, Target, TrendingUp, Info } from 'lucide-react'

import { useSampleContext } from '../context/SampleContext'
import { useApi } from '../hooks/useApi'
import { getPrediction, getForecast } from '../services/api'

import MetricCard from '../components/MetricCard'
import Panel from '../components/Panel'
import StageBadge from '../components/StageBadge'
import MitreBadge from '../components/MitreBadge'
import RiskIndicator from '../components/RiskIndicator'
import AlertCard from '../components/AlertCard'
import LoadingSkeleton, { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'
import { STAGE_COLORS, fmtPct, fmtPctShort, type AttackStageKey } from '../utils/constants'

// ── Custom tooltip for recharts ───────────────────────────────────────────────
function ForecastTooltip({ active, payload, label }: {
  active?: boolean; payload?: Array<{ value: number }>; label?: string
}) {
  if (!active || !payload?.length) return null
  const val = payload[0].value as number
  return (
    <div style={{
      background: '#0d1526', border: '1px solid #1a2c4a',
      borderRadius: 6, padding: '8px 12px', fontSize: '0.78rem',
    }}>
      <div style={{ color: '#7d95b5', marginBottom: 3 }}>{label}</div>
      <div style={{ color: '#e2e8f0', fontWeight: 700 }}>
        Attack Probability: <span style={{ color: '#ef4444' }}>{fmtPct(val)}</span>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])

  const pred     = useApi(() => getPrediction(sampleId), deps)
  const forecast = useApi(() => getForecast(sampleId),   deps)

  // Forecast chart data
  const chartData = useMemo(() => {
    if (!forecast.data) return []
    return forecast.data.forecast.map(f => ({
      name:  `Step ${f.step}`,
      prob:  f.attack_probability,
      stage: f.stage,
    }))
  }, [forecast.data])

  const loading = pred.loading || forecast.loading
  const error   = pred.error || forecast.error

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Page header ── */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: 0 }}>
          SOC Dashboard
        </h1>
        <span style={{ color: '#1e3a5f', fontSize: '0.8rem' }}>
          — Sample #{sampleId}
        </span>
      </div>

      {/* ── Error ── */}
      {error && !loading && (
        <ErrorState error={error} onRetry={pred.refetch} />
      )}

      {/* ── Top metric cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
        ) : pred.data ? (
          <>
            <MetricCard
              label="Attack Probability"
              value={fmtPct(pred.data.attack_probability)}
              sub={pred.data.attack_detected ? '⚠ Attack Detected' : '✓ No Attack'}
              accentColor={pred.data.attack_probability > 0.7 ? '#ef4444' : pred.data.attack_probability > 0.3 ? '#f59e0b' : '#22c55e'}
              icon={<Zap size={16} />}
            />
            <MetricCard
              label="Predicted Stage"
              value={<StageBadge stage={pred.data.predicted_stage} size="lg" />}
              sub="Model prediction"
              accentColor={STAGE_COLORS[pred.data.predicted_stage as AttackStageKey] ?? '#3b82f6'}
              icon={<Target size={16} />}
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
        ) : null}
      </div>

      {/* ── Main content grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 16 }}>

        {/* Left: forecast chart */}
        <Panel
          title="Attack Risk Forecast"
          subtitle="5-step autoregressive prediction — no ground truth used"
        >
          {forecast.loading ? (
            <LoadingSkeleton lines={5} height={220} />
          ) : forecast.error ? (
            <ErrorState error={forecast.error} onRetry={forecast.refetch} compact />
          ) : forecast.data ? (
            <div>
              {/* Ground truth note */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 5,
                marginBottom: 10, padding: '5px 10px',
                background: forecast.data.ground_truth_used
                  ? 'rgba(245,158,11,0.08)' : 'rgba(34,197,94,0.06)',
                border: `1px solid ${forecast.data.ground_truth_used ? '#f59e0b33' : '#22c55e33'}`,
                borderRadius: 5, fontSize: '0.72rem',
                color: forecast.data.ground_truth_used ? '#f59e0b' : '#4ade80',
              }}>
                <Info size={11} />
                Ground truth used: <strong>{forecast.data.ground_truth_used ? 'Yes' : 'No'}</strong>
                {!forecast.data.ground_truth_used && ' — genuine autoregressive forecast'}
              </div>

              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
                  <defs>
                    <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
                  <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
                  <YAxis
                    domain={[0, 1]} tickFormatter={v => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: '#3d5275', fontSize: 11 }}
                  />
                  <Tooltip content={<ForecastTooltip />} />
                  <ReferenceLine y={0.5} stroke="#f59e0b" strokeDasharray="4 3"
                    label={{ value: '50% threshold', fill: '#f59e0b', fontSize: 10, position: 'right' }} />
                  <ReferenceLine y={0.7} stroke="#ef444466" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="prob" stroke="#ef4444" strokeWidth={2}
                    fill="url(#riskGrad)" dot={{ fill: '#ef4444', r: 4 }} />
                </AreaChart>
              </ResponsiveContainer>

              {/* Risk legend */}
              <div style={{ display: 'flex', gap: 16, marginTop: 8, justifyContent: 'center' }}>
                {[['#22c55e', '0–30%', 'LOW'], ['#f59e0b', '30–70%', 'MEDIUM'], ['#ef4444', '70–100%', 'HIGH']].map(
                  ([color, range, label]) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
                      <span style={{ color: '#3d5275', fontSize: '0.68rem' }}>{range} {label}</span>
                    </div>
                  )
                )}
              </div>
            </div>
          ) : null}
        </Panel>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Risk indicator */}
          <Panel title="Overall Risk">
            {pred.loading ? <LoadingSkeleton lines={3} height={80} /> :
             pred.data ? (
               <RiskIndicator probability={pred.data.attack_probability} size="lg" />
             ) : null}
          </Panel>

          {/* Prediction detail */}
          <Panel title="Prediction Detail">
            {pred.loading ? <LoadingSkeleton lines={4} height={100} /> :
             pred.data ? (
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
                 <div style={{
                   marginTop: 4, padding: '5px 8px',
                   background: 'rgba(59,130,246,0.06)', borderRadius: 4,
                   color: '#2a5070', fontSize: '0.65rem',
                 }}>
                   Representative mapping — prototype stage-to-technique assignment.
                   Not direct ATT&CK technique detection.
                 </div>
               </div>
             ) : null}
          </Panel>
        </div>
      </div>

      {/* ── Alert ── */}
      {pred.data && pred.data.attack_detected && (
        <AlertCard
          attackProbability={pred.data.attack_probability}
          predictedStage={pred.data.predicted_stage}
          mitreId={pred.data.mitre_attack_id}
          mitreName={pred.data.mitre_attack_name}
          sampleId={sampleId}
        />
      )}

      {/* ── Forecast step summary ── */}
      {forecast.data && (
        <Panel title="Forecast Step Summary" subtitle="All 5 predicted steps">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
            {forecast.data.forecast.map(step => {
              const stageColor = STAGE_COLORS[step.stage as AttackStageKey] ?? '#7d95b5'
              return (
                <div key={step.step} style={{
                  background: '#070d1a',
                  border: `1px solid ${stageColor}33`,
                  borderTop: `2px solid ${stageColor}`,
                  borderRadius: 7, padding: '10px 10px 8px',
                  display: 'flex', flexDirection: 'column', gap: 6,
                }}>
                  <div style={{ color: '#3d5275', fontSize: '0.65rem', fontWeight: 700 }}>
                    STEP {step.step}
                  </div>
                  <StageBadge stage={step.stage} size="sm" />
                  <div style={{ color: stageColor, fontSize: '1rem', fontWeight: 800 }}>
                    {fmtPctShort(step.attack_probability)}
                  </div>
                  <div style={{ color: '#2a4060', fontSize: '0.65rem' }}>
                    conf: {fmtPctShort(step.stage_confidence)}
                  </div>
                </div>
              )
            })}
          </div>
        </Panel>
      )}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ color: '#3d5275', fontSize: '0.75rem' }}>{label}</span>
      {children}
    </div>
  )
}
