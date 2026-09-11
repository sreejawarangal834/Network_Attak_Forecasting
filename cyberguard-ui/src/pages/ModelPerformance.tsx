/**
 * ModelPerformance.tsx — Global model evaluation page.
 *
 * Data source: GET /model/comparison (always — no dependency on uploaded analysis).
 *
 * Actual backend response: a plain JSON ARRAY (not a wrapper object):
 *   [
 *     { Model, Temporal_History, Attack_Accuracy, Attack_Precision,
 *       Attack_Recall, Attack_F1, Stage_Accuracy, Stage_Macro_F1 },
 *     ...
 *   ]
 *
 * Some baseline metrics are legitimately absent ("N/A" string from the CSV).
 * These are shown as "—" in the table and omitted from the chart bars
 * (not plotted as 0).
 *
 * Nothing is hard-coded. All values originate from GET /model/comparison.
 */

import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { Info } from 'lucide-react'

import { useApi }            from '../hooks/useApi'
import { getModelComparison } from '../services/api'

import Panel      from '../components/Panel'
import MetricCard from '../components/MetricCard'
import { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

// ── Types ─────────────────────────────────────────────────────────────────────

/** One row from the CSV, after pandas fillna("N/A"). */
interface CompRow {
  Model:            string
  Temporal_History: string
  Attack_Accuracy:  number | 'N/A'
  Attack_Precision: number | 'N/A'
  Attack_Recall:    number | 'N/A'
  Attack_F1:        number | 'N/A'
  Stage_Accuracy:   number | 'N/A'
  Stage_Macro_F1:   number | 'N/A'
  /** Optional extended metrics if added later */
  [key: string]:    number | string
}

// ── Constants ─────────────────────────────────────────────────────────────────

/**
 * Metrics to display — must match CSV column names exactly.
 * short is the X-axis tick label in the chart.
 */
const METRIC_DEFS = [
  { key: 'Attack_Accuracy',  label: 'Attack Accuracy',  short: 'Atk Acc'  },
  { key: 'Attack_Precision', label: 'Attack Precision', short: 'Atk Prec' },
  { key: 'Attack_Recall',    label: 'Attack Recall',    short: 'Atk Rec'  },
  { key: 'Attack_F1',        label: 'Attack F1',        short: 'Atk F1'   },
  { key: 'Stage_Accuracy',   label: 'Stage Accuracy',   short: 'Stg Acc'  },
  { key: 'Stage_Macro_F1',   label: 'Stage Macro F1',   short: 'Stg F1'   },
] as const

/** Colour palette — index 0 = first model, index 1 = second model, etc. */
const MODEL_COLORS = ['#6b7280', '#3b82f6', '#06b6d4', '#8b5cf6']

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Convert a raw API field to a number, or null when it is "N/A" / missing. */
function toNum(v: number | string | undefined): number | null {
  if (v === undefined || v === null) return null
  if (typeof v === 'number' && isFinite(v)) return v
  if (typeof v === 'string' && v.trim().toUpperCase() === 'N/A') return null
  const n = parseFloat(String(v))
  return isFinite(n) ? n : null
}

/** Format a metric value as a percentage string, or "—" for nulls. */
function fmtMetric(v: number | null): string {
  if (v === null) return '—'
  return `${(v * 100).toFixed(2)}%`
}

// ── Chart data builder ────────────────────────────────────────────────────────
/**
 * Transforms the raw array returned by /model/comparison into the shape
 * Recharts needs:
 *
 *   [
 *     { metric: "Atk Acc", model_0: 94.34, model_1: 94.95 },
 *     { metric: "Atk Prec", model_0: null, model_1: 97.65 },  // null → bar hidden
 *     ...
 *   ]
 *
 * Null values are included in the array so the chart can skip them cleanly.
 * The Bar component receives a custom <Cell> that sets opacity=0 for nulls.
 */
function buildChartData(rows: CompRow[]) {
  return METRIC_DEFS.map(({ key, short }) => {
    const entry: Record<string, string | number | null> = { metric: short }
    rows.forEach((row, i) => {
      const n = toNum(row[key])
      // Multiply by 100 for percentage display; keep null as null (not 0)
      entry[`model_${i}`] = n !== null ? parseFloat((n * 100).toFixed(2)) : null
    })
    return entry
  })
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

function CustomTooltip({ active, payload, label }: {
  active?: boolean
  payload?: Array<{ name: string; value: number | null; color: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#0d1526', border: '1px solid #1a2c4a',
      borderRadius: 6, padding: '8px 12px', fontSize: '0.78rem',
    }}>
      <div style={{ color: '#7d95b5', marginBottom: 4, fontWeight: 600 }}>{label}</div>
      {payload.map(p => (
        <div key={p.name} style={{ color: p.color, marginBottom: 2 }}>
          {p.name}: {p.value !== null ? `${p.value?.toFixed(2)}%` : '—'}
        </div>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ModelPerformance() {
  /**
   * The backend returns a plain JSON array — NOT a wrapper object.
   * `comp.data` IS the array itself.
   */
  const comp = useApi(() => getModelComparison(), [])

  const rows: CompRow[] = useMemo(() => {
    if (!comp.data) return []
    // Defensive: handle both plain array (correct) and wrapped {value:[]} (legacy/mock)
    if (Array.isArray(comp.data)) return comp.data as CompRow[]
    const wrapped = comp.data as { value?: CompRow[] }
    if (Array.isArray(wrapped.value)) return wrapped.value
    return []
  }, [comp.data])

  const chartData = useMemo(() => buildChartData(rows), [rows])

  // Per-metric delta: Transformer (last row) vs Logistic Regression (first row)
  const baselineRow    = rows[0]
  const transformerRow = rows[rows.length - 1]

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Page header */}
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Model Performance
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Temporal Transformer vs baseline — all metrics from the real evaluation set
        </p>
      </div>

      {/* Loading */}
      {comp.loading && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <CardSkeleton /><CardSkeleton />
        </div>
      )}

      {/* Error */}
      {comp.error && !comp.loading && (
        <ErrorState error={comp.error} onRetry={comp.refetch} />
      )}

      {/* Loaded — rows present */}
      {!comp.loading && !comp.error && rows.length > 0 && (
        <>
          {/* Model headline cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
            {rows.map((row, i) => (
              <div key={row.Model} style={{
                background: '#0d1526',
                border: `1px solid ${(MODEL_COLORS[i] ?? '#1a2c4a')}44`,
                borderTop: `3px solid ${MODEL_COLORS[i] ?? '#1a2c4a'}`,
                borderRadius: 10, padding: '16px',
              }}>
                <div style={{
                  color: MODEL_COLORS[i] ?? '#7d95b5',
                  fontSize: '0.78rem', fontWeight: 700, marginBottom: 12,
                }}>
                  {row.Model}
                  {row.Model.toLowerCase().includes('transformer') && (
                    <span style={{
                      marginLeft: 8, background: '#3b82f616',
                      border: '1px solid #3b82f644', borderRadius: 4,
                      padding: '1px 7px', fontSize: '0.62rem',
                    }}>
                      PRIMARY
                    </span>
                  )}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  {METRIC_DEFS.map(({ key, label }) => (
                    <div key={key}>
                      <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        {label}
                      </div>
                      <div style={{
                        color: MODEL_COLORS[i] ?? '#7d95b5',
                        fontSize: '1.05rem', fontWeight: 800, marginTop: 2,
                      }}>
                        {fmtMetric(toNum(row[key]))}
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 10, color: '#1e3a5f', fontSize: '0.68rem' }}>
                  Temporal History: {row.Temporal_History}
                </div>
              </div>
            ))}
          </div>

          {/* Improvement delta cards */}
          {transformerRow && baselineRow && transformerRow !== baselineRow && (
            <Panel title="Performance Improvement (Transformer vs Baseline)">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
                {METRIC_DEFS.map(({ key, label }) => {
                  const tVal = toNum(transformerRow[key])
                  const bVal = toNum(baselineRow[key])
                  if (tVal === null) return (
                    <MetricCard key={key} label={label} value="—" sub="No data" accentColor="#3d5275" />
                  )
                  if (bVal === null) return (
                    <MetricCard key={key} label={label} value={fmtMetric(tVal)} sub="Baseline N/A" accentColor="#3b82f6" />
                  )
                  const delta = tVal - bVal
                  return (
                    <MetricCard
                      key={key}
                      label={label}
                      value={delta >= 0 ? `+${(delta * 100).toFixed(1)}pp` : `${(delta * 100).toFixed(1)}pp`}
                      sub={`${fmtMetric(tVal)} vs ${fmtMetric(bVal)}`}
                      accentColor={delta > 0 ? '#22c55e' : '#ef4444'}
                    />
                  )
                })}
              </div>
            </Panel>
          )}

          {/* Metric comparison bar chart */}
          <Panel
            title="Metric Comparison Chart"
            subtitle="All values from GET /model/comparison — no fabricated metrics. '—' = not available for this model."
          >
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={chartData}
                margin={{ top: 8, right: 24, bottom: 0, left: -8 }}
                barGap={4}
                barCategoryGap="25%"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
                <XAxis
                  dataKey="metric"
                  tick={{ fill: '#3d5275', fontSize: 11 }}
                />
                <YAxis
                  domain={[0, 100]}
                  tickFormatter={v => `${v}%`}
                  tick={{ fill: '#3d5275', fontSize: 11 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  formatter={(value: string) => (
                    <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>{value}</span>
                  )}
                />
                {rows.map((row, i) => (
                  <Bar
                    key={row.Model}
                    dataKey={`model_${i}`}
                    name={row.Model}
                    fill={MODEL_COLORS[i] ?? '#7d95b5'}
                    radius={[3, 3, 0, 0]}
                    maxBarSize={48}
                  >
                    {chartData.map((entry, idx) => {
                      const val = entry[`model_${i}`]
                      return (
                        <Cell
                          key={`cell-${idx}`}
                          fillOpacity={val !== null ? 0.85 : 0}
                        />
                      )
                    })}
                  </Bar>
                ))}
              </BarChart>
            </ResponsiveContainer>

            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 5, color: '#1e3a5f', fontSize: '0.68rem' }}>
              <Info size={11} />
              Bars with opacity 0 indicate "N/A" in the CSV (metric not computed for that model).
            </div>
          </Panel>

          {/* Full comparison table — readable fallback */}
          <Panel title="Full Comparison Table">
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th style={TH}>Metric</th>
                    {rows.map(row => (
                      <th key={row.Model} style={TH}>{row.Model}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {/* Temporal history row */}
                  <tr style={{ background: '#070d1a' }}>
                    <td style={{ ...TD, color: '#5d7a9a', fontStyle: 'italic' }}>Temporal History</td>
                    {rows.map(row => (
                      <td key={row.Model} style={{ ...TD, color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                        {row.Temporal_History}
                      </td>
                    ))}
                  </tr>
                  {/* Metric rows */}
                  {METRIC_DEFS.map(({ key, label }, idx) => (
                    <tr key={key} style={{ background: idx % 2 === 0 ? 'transparent' : '#070d1a' }}>
                      <td style={{ ...TD, color: '#c8d8ec', fontWeight: 600 }}>{label}</td>
                      {rows.map((row, i) => {
                        const n = toNum(row[key])
                        return (
                          <td key={row.Model} style={{
                            ...TD,
                            color: n !== null ? (MODEL_COLORS[i] ?? '#c8d8ec') : '#2a4060',
                            fontFamily: 'monospace',
                            fontWeight: n !== null ? 700 : 400,
                          }}>
                            {fmtMetric(n)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 5, color: '#1e3a5f', fontSize: '0.68rem' }}>
              <Info size={11} />
              Values sourced directly from GET /model/comparison. "—" means the metric was not computed for that model (N/A in CSV). No values fabricated.
            </div>
          </Panel>
        </>
      )}

      {/* Loaded — but empty response */}
      {!comp.loading && !comp.error && rows.length === 0 && (
        <div style={{
          padding: '32px 24px', textAlign: 'center',
          background: '#0d1526', border: '1px solid #1a2c4a',
          borderRadius: 8, color: '#3d5275', fontSize: '0.85rem',
        }}>
          No comparison data returned from <code style={{ color: '#60a5fa' }}>GET /model/comparison</code>.
          <br />
          <span style={{ fontSize: '0.75rem', color: '#1e3a5f' }}>
            Ensure <code>results/model_comparison.csv</code> exists in the project root.
          </span>
        </div>
      )}
    </div>
  )
}

// ── Shared table styles ────────────────────────────────────────────────────────

const TH: React.CSSProperties = {
  textAlign: 'left', padding: '7px 12px',
  color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase',
  letterSpacing: '0.06em', borderBottom: '1px solid #1a2c4a',
  whiteSpace: 'nowrap',
}

const TD: React.CSSProperties = {
  padding: '8px 12px',
  borderBottom: '1px solid #0f1d33',
  fontSize: '0.8rem', whiteSpace: 'nowrap',
}
