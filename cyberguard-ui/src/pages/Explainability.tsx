/**
 * Explainability.tsx — Feature sensitivity analysis page.
 *
 * Consumes: GET /explain/{sample_id}
 *
 * IMPORTANT LANGUAGE: "sensitivity" = prediction influence.
 * The backend explicitly states this does NOT establish causation.
 * This disclaimer is shown prominently and unavoidably.
 */

import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { AlertTriangle, Info } from 'lucide-react'

import { useSampleContext } from '../context/SampleContext'
import { useApi } from '../hooks/useApi'
import { getExplanation } from '../services/api'

import Panel from '../components/Panel'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

// Gradient from high → low sensitivity
const SENSITIVITY_COLORS = [
  '#ef4444', '#f97316', '#f59e0b',
  '#eab308', '#84cc16', '#22c55e',
  '#06b6d4', '#3b82f6', '#8b5cf6', '#7d95b5',
]

export default function Explainability() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps  = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const expl  = useApi(() => getExplanation(sampleId), deps)

  // Top 10 features for chart
  const chartData = useMemo(() => {
    if (!expl.data) return []
    return expl.data.features
      .slice(0, 10)
      .sort((a, b) => a.sensitivity - b.sensitivity) // ascending so highest is at top in horizontal bar
      .map(f => ({
        name:        f.feature.length > 26 ? f.feature.slice(0, 24) + '…' : f.feature,
        fullName:    f.feature,
        sensitivity: parseFloat(f.sensitivity.toFixed(6)),
        rank:        f.rank,
      }))
  }, [expl.data])

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Explainability
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Feature sensitivity analysis — which features most influence the model's prediction
        </p>
      </div>

      {/* Causation disclaimer — always visible */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 10,
        padding: '12px 16px',
        background: 'rgba(245,158,11,0.06)',
        border: '1px solid rgba(245,158,11,0.22)',
        borderRadius: 8,
      }}>
        <AlertTriangle size={16} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />
        <div>
          <div style={{ color: '#f59e0b', fontSize: '0.78rem', fontWeight: 700, marginBottom: 3 }}>
            Interpretation Warning
          </div>
          <div style={{ color: '#7d8a6a', fontSize: '0.75rem', lineHeight: 1.5 }}>
            {expl.data?.warning ??
              'Sensitivity indicates prediction influence and does not establish causation.'}
            {' '}High sensitivity means the model's output changes significantly when a
            feature is removed — it does <strong>not</strong> mean that feature caused the attack.
          </div>
        </div>
      </div>

      {expl.error && !expl.loading && (
        <ErrorState error={expl.error} onRetry={expl.refetch} />
      )}

      {/* Method badge */}
      {expl.data && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#3d5275', fontSize: '0.72rem' }}>Method:</span>
          <span style={{
            background: 'rgba(59,130,246,0.10)', border: '1px solid rgba(59,130,246,0.25)',
            borderRadius: 5, padding: '2px 10px',
            color: '#60a5fa', fontSize: '0.72rem', fontFamily: 'monospace',
          }}>
            {expl.data.method}
          </span>
          <span style={{ color: '#1e3a5f', fontSize: '0.68rem' }}>
            Sample #{sampleId}
          </span>
        </div>
      )}

      {/* Horizontal bar chart */}
      <Panel
        title="Top 10 Prediction-Sensitive Features"
        subtitle="Sorted by sensitivity score — higher bar = greater prediction influence"
      >
        {expl.loading ? <LoadingSkeleton lines={6} height={300} /> :
         expl.data ? (
          <div>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 4, right: 40, bottom: 4, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: '#3d5275', fontSize: 10 }}
                  tickFormatter={v => v.toFixed(3)}
                />
                <YAxis
                  type="category" dataKey="name" width={160}
                  tick={{ fill: '#7d95b5', fontSize: 10.5 }}
                />
                <Tooltip
                  contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
                  formatter={(v: unknown, _: unknown, props: { payload?: { fullName: string; rank: number } }) => [
                    (typeof v === 'number' ? v : 0).toFixed(6),
                    `Sensitivity (Rank #${props.payload?.rank ?? ''}: ${props.payload?.fullName ?? ''})`,
                  ] as [string, string]}
                />
                <Bar dataKey="sensitivity" radius={[0, 4, 4, 0]}>
                  {chartData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={SENSITIVITY_COLORS[Math.min(i, SENSITIVITY_COLORS.length - 1)]}
                      fillOpacity={0.85}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            {/* Explanation of the chart */}
            <div style={{
              marginTop: 10, display: 'flex', alignItems: 'flex-start', gap: 6,
              padding: '8px 10px', background: 'rgba(59,130,246,0.04)',
              borderRadius: 5, color: '#2a5070', fontSize: '0.72rem',
            }}>
              <Info size={12} style={{ marginTop: 1, flexShrink: 0 }} />
              Feature sensitivity measures how much the model's prediction changes
              when that feature's information is removed (ablation).
              It quantifies prediction influence — not causal attribution.
            </div>
          </div>
        ) : null}
      </Panel>

      {/* Full ranked table */}
      {expl.data && (
        <Panel title="Full Feature Sensitivity Ranking">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  {['Rank', 'Feature', 'Sensitivity', 'Relative Influence'].map(h => (
                    <th key={h} style={{
                      textAlign: 'left', padding: '6px 10px',
                      color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase',
                      letterSpacing: '0.06em', borderBottom: '1px solid #1a2c4a',
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {expl.data.features.map((f, i) => {
                  const rel  = f.sensitivity / (expl.data!.features[0]?.sensitivity || 1)
                  const barW = `${rel * 100}%`
                  const col  = SENSITIVITY_COLORS[Math.min(i, SENSITIVITY_COLORS.length - 1)]
                  return (
                    <tr key={f.rank} style={{ background: i % 2 === 0 ? 'transparent' : '#070d1a' }}>
                      <td style={{ padding: '7px 10px', color: '#3d5275', fontFamily: 'monospace', width: 50 }}>
                        #{f.rank}
                      </td>
                      <td style={{ padding: '7px 10px', color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                        {f.feature}
                      </td>
                      <td style={{ padding: '7px 10px', color: col, fontFamily: 'monospace', fontWeight: 700 }}>
                        {f.sensitivity.toFixed(6)}
                      </td>
                      <td style={{ padding: '7px 10px', minWidth: 140 }}>
                        <div style={{ height: 6, background: '#0f1d33', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', width: barW,
                            background: col, borderRadius: 3,
                          }} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  )
}
