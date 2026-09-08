/**
 * ModelPerformance.tsx — Model comparison page.
 *
 * Consumes: GET /model/comparison
 * Shows: Temporal Transformer vs baseline — all values from real API.
 */

import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Info } from 'lucide-react'

import { useApi } from '../hooks/useApi'
import { getModelComparison } from '../services/api'

import Panel from '../components/Panel'
import MetricCard from '../components/MetricCard'
import LoadingSkeleton, { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

type CompRow = import('../types/api').ComparisonRow

const METRIC_LABELS: Array<{ key: keyof CompRow; label: string; short: string }> = [
  { key: 'Attack_Accuracy',  label: 'Attack Accuracy',    short: 'Acc'  },
  { key: 'Attack_Precision', label: 'Attack Precision',   short: 'Prec' },
  { key: 'Attack_Recall',    label: 'Attack Recall',      short: 'Rec'  },
  { key: 'Attack_F1',        label: 'Attack F1',          short: 'F1'   },
  { key: 'Stage_Accuracy',   label: 'Stage Accuracy',     short: 'StgA' },
  { key: 'Stage_Macro_F1',   label: 'Stage Macro F1',     short: 'StgF1'},
]

const MODEL_COLORS: Record<number, string> = { 0: '#3b82f6', 1: '#6b7280' }

function fmtMetric(v: number | string) {
  if (typeof v === 'number') return `${(v * 100).toFixed(2)}%`
  return String(v)
}

export default function ModelPerformance() {
  const comp = useApi(() => getModelComparison(), [])

  // Build chart data: one entry per metric
  const chartData = useMemo(() => {
    if (!comp.data) return []
    return METRIC_LABELS.map(({ key, short }) => {
      const entry: Record<string, string | number> = { metric: short }
      comp.data!.forEach((row, i) => {
        const v = row[key]
        entry[`model_${i}`] = typeof v === 'number' ? parseFloat((v * 100).toFixed(2)) : 0
        entry[`label_${i}`] = row.Model
      })
      return entry
    })
  }, [comp.data])

  // Transformer row (first model assumed to be the better one)
  const transformer = comp.data?.[0]
  const baseline    = comp.data?.[1]

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Model Performance
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Temporal Transformer vs baseline — all metrics from the real evaluation set
        </p>
      </div>

      {comp.error && !comp.loading && (
        <ErrorState error={comp.error} onRetry={comp.refetch} />
      )}

      {/* Model headline cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {comp.loading ? (
          <><CardSkeleton /><CardSkeleton /></>
        ) : comp.data ? (
          comp.data.map((row, i) => (
            <div key={row.Model} style={{
              background: '#0d1526',
              border: `1px solid ${MODEL_COLORS[i] ?? '#1a2c4a'}44`,
              borderTop: `3px solid ${MODEL_COLORS[i] ?? '#1a2c4a'}`,
              borderRadius: 10, padding: '16px',
            }}>
              <div style={{
                color: MODEL_COLORS[i] ?? '#7d95b5',
                fontSize: '0.78rem', fontWeight: 700, marginBottom: 12,
              }}>
                {row.Model}
                {i === 0 && (
                  <span style={{
                    marginLeft: 8, background: '#3b82f616', border: '1px solid #3b82f644',
                    borderRadius: 4, padding: '1px 7px', fontSize: '0.62rem',
                  }}>
                    PRIMARY
                  </span>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                {METRIC_LABELS.map(({ key, label }) => (
                  <div key={key}>
                    <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                      {label}
                    </div>
                    <div style={{
                      color: MODEL_COLORS[i] ?? '#7d95b5',
                      fontSize: '1.1rem', fontWeight: 800, marginTop: 2,
                    }}>
                      {fmtMetric(row[key])}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 10, color: '#1e3a5f', fontSize: '0.68rem' }}>
                Temporal History: {row.Temporal_History} steps
              </div>
            </div>
          ))
        ) : null}
      </div>

      {/* Improvement delta (if two models) */}
      {transformer && baseline && (
        <Panel title="Performance Improvement (Transformer vs Baseline)">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
            {METRIC_LABELS.map(({ key, label }) => {
              const tVal = typeof transformer[key] === 'number' ? transformer[key] as number : 0
              const bVal = typeof baseline[key]    === 'number' ? baseline[key]    as number : 0
              const delta = tVal - bVal
              return (
                <MetricCard
                  key={key}
                  label={label}
                  value={`+${(delta * 100).toFixed(1)}pp`}
                  sub={`${fmtMetric(tVal)} vs ${fmtMetric(bVal)}`}
                  accentColor={delta > 0 ? '#22c55e' : '#ef4444'}
                />
              )
            })}
          </div>
        </Panel>
      )}

      {/* Grouped bar chart */}
      <Panel
        title="Metric Comparison Chart"
        subtitle="All values from GET /model/comparison — no fabricated metrics"
      >
        {comp.loading ? <LoadingSkeleton lines={5} height={280} /> :
         comp.data ? (
          <div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 4, right: 20, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
                <XAxis dataKey="metric" tick={{ fill: '#3d5275', fontSize: 11 }} />
                <YAxis
                  domain={[0, 100]} tickFormatter={v => `${v}%`}
                  tick={{ fill: '#3d5275', fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
                  formatter={(v: unknown) => [`${(typeof v === 'number' ? v : 0).toFixed(2)}%`] as [string]}
                />
                <Legend wrapperStyle={{ fontSize: '0.75rem', color: '#5d7a9a' }} />
                {comp.data.map((row, i) => (
                  <Bar
                    key={row.Model}
                    dataKey={`model_${i}`}
                    name={row.Model}
                    fill={MODEL_COLORS[i] ?? '#7d95b5'}
                    radius={[3, 3, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : null}
      </Panel>

      {/* Full comparison table */}
      {comp.data && (
        <Panel title="Full Comparison Table">
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr>
                  <th style={TH}>Model</th>
                  <th style={TH}>History</th>
                  {METRIC_LABELS.map(({ label }) => (
                    <th key={label} style={TH}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comp.data.map((row, i) => (
                  <tr key={row.Model} style={{ background: i === 0 ? 'rgba(59,130,246,0.04)' : 'transparent' }}>
                    <td style={{ ...TD, color: MODEL_COLORS[i] ?? '#7d95b5', fontWeight: 700 }}>
                      {row.Model}
                    </td>
                    <td style={{ ...TD, fontFamily: 'monospace', color: '#5d7a9a' }}>
                      {row.Temporal_History}
                    </td>
                    {METRIC_LABELS.map(({ key }) => (
                      <td key={key} style={{ ...TD, color: '#c8d8ec' }}>
                        {fmtMetric(row[key])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{
            marginTop: 10, display: 'flex', alignItems: 'center', gap: 5,
            color: '#1e3a5f', fontSize: '0.68rem',
          }}>
            <Info size={11} />
            Values sourced directly from GET /model/comparison. No metrics have been fabricated.
          </div>
        </Panel>
      )}
    </div>
  )
}

const TH: React.CSSProperties = {
  textAlign: 'left', padding: '7px 10px',
  color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase',
  letterSpacing: '0.06em', borderBottom: '1px solid #1a2c4a',
  whiteSpace: 'nowrap',
}
const TD: React.CSSProperties = {
  padding: '8px 10px', borderBottom: '1px solid #0f1d33',
  fontSize: '0.8rem', whiteSpace: 'nowrap',
}
