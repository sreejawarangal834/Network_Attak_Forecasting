/**
 * Explainability.tsx — Feature sensitivity analysis page.
 *
 * PRIMARY MODE (uploaded analysis in AnalysisContext):
 *   Data: analysis.explainability from context (already fetched, no extra call).
 *   Displays feature sensitivity for the current uploaded analysis.
 *   Backend warning is preserved and shown prominently.
 *
 * FALLBACK MODE (no analysis):
 *   Upload prompt + Developer/Demo section (GET /explain/{sample_id}).
 *
 * IMPORTANT: sensitivity = prediction influence, NOT causation.
 * This disclaimer is always visible.
 */

import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { AlertTriangle, Info, UploadCloud, ChevronDown } from 'lucide-react'

import { useAnalysisContext } from '../context/AnalysisContext'
import { useSampleContext }   from '../context/SampleContext'
import { useApi }             from '../hooks/useApi'
import { getExplanation }     from '../services/api'

import Panel      from '../components/Panel'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

const SENSITIVITY_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#7d95b5',
]

// ─────────────────────────────────────────────────────────────────────────────
// Shared chart + table (accepts any feature list)
// ─────────────────────────────────────────────────────────────────────────────

interface ExplainData {
  rank:        number
  feature:     string
  sensitivity: number
}

interface ExplainViewProps {
  features: ExplainData[]
  method:   string
  warning:  string
  scopeNote?: string   // additional context about prediction scope
}

function ExplainView({ features, method, warning, scopeNote }: ExplainViewProps) {
  const chartData = useMemo(() =>
    features.slice(0, 10)
      .sort((a, b) => a.sensitivity - b.sensitivity)
      .map(f => ({
        name:        f.feature.length > 26 ? f.feature.slice(0, 24) + '…' : f.feature,
        fullName:    f.feature,
        sensitivity: parseFloat(f.sensitivity.toFixed(6)),
        rank:        f.rank,
      })),
  [features])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Method + scope */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ color: '#3d5275', fontSize: '0.72rem' }}>Method:</span>
        <span style={{ background: 'rgba(59,130,246,0.10)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 5, padding: '2px 10px', color: '#60a5fa', fontSize: '0.72rem', fontFamily: 'monospace' }}>
          {method}
        </span>
        {scopeNote && (
          <span style={{ color: '#2a4060', fontSize: '0.68rem' }}>{scopeNote}</span>
        )}
      </div>

      {/* Horizontal bar chart */}
      <Panel title="Top 10 Prediction-Sensitive Features" subtitle="Sorted by sensitivity — higher bar = greater prediction influence">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" horizontal={false} />
            <XAxis type="number" tick={{ fill: '#3d5275', fontSize: 10 }} tickFormatter={v => v.toFixed(3)} />
            <YAxis type="category" dataKey="name" width={160} tick={{ fill: '#7d95b5', fontSize: 10.5 }} />
            <Tooltip
              contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
              formatter={(v: unknown, _: unknown, p: { payload?: { fullName: string; rank: number } }) => [
                (typeof v === 'number' ? v : 0).toFixed(6),
                `Sensitivity (Rank #${p.payload?.rank ?? ''}: ${p.payload?.fullName ?? ''})`,
              ] as [string, string]}
            />
            <Bar dataKey="sensitivity" radius={[0, 4, 4, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={SENSITIVITY_COLORS[Math.min(i, SENSITIVITY_COLORS.length - 1)]} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'flex-start', gap: 6, padding: '8px 10px', background: 'rgba(59,130,246,0.04)', borderRadius: 5, color: '#2a5070', fontSize: '0.72rem' }}>
          <Info size={12} style={{ marginTop: 1, flexShrink: 0 }} />
          Feature sensitivity measures how much the model's prediction changes when that feature's information is removed (ablation). It quantifies prediction influence — not causal attribution.
        </div>
      </Panel>

      {/* Full ranked table */}
      <Panel title="Full Feature Sensitivity Ranking">
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr>
                {['Rank', 'Feature', 'Sensitivity', 'Relative Influence'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 10px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid #1a2c4a' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {features.map((f, i) => {
                const rel  = f.sensitivity / (features[0]?.sensitivity || 1)
                const col  = SENSITIVITY_COLORS[Math.min(i, SENSITIVITY_COLORS.length - 1)]
                return (
                  <tr key={f.rank} style={{ background: i % 2 === 0 ? 'transparent' : '#070d1a' }}>
                    <td style={{ padding: '7px 10px', color: '#3d5275', fontFamily: 'monospace', width: 50 }}>#{f.rank}</td>
                    <td style={{ padding: '7px 10px', color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.75rem' }}>{f.feature}</td>
                    <td style={{ padding: '7px 10px', color: col, fontFamily: 'monospace', fontWeight: 700 }}>{f.sensitivity.toFixed(6)}</td>
                    <td style={{ padding: '7px 10px', minWidth: 140 }}>
                      <div style={{ height: 6, background: '#0f1d33', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${rel * 100}%`, background: col, borderRadius: 3 }} />
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 5, color: '#1e3a5f', fontSize: '0.68rem' }}>
          <Info size={11} />
          {warning}
        </div>
      </Panel>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Primary view — analysis context
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisExplainView() {
  const { analysis } = useAnalysisContext()

  const raw = analysis?.explainability ?? []
  const features: ExplainData[] = raw.map((f, i) => ({
    rank:        i + 1,
    feature:     f.feature,
    sensitivity: f.sensitivity,
  }))

  if (features.length === 0) {
    return <div style={{ padding: '32px', textAlign: 'center', color: '#3d5275', background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 8 }}>No explainability data in this analysis.</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 7 }}>
        <span style={{ color: '#4ade80', fontSize: '0.78rem', fontWeight: 600 }}>Live Analysis</span>
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem' }}>{analysis?.input.filename}</span>
      </div>
      <ExplainView
        features={features}
        method="feature_ablation_sensitivity"
        warning="Sensitivity indicates prediction influence and does not establish causation."
        scopeNote="network-level prediction"
      />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Dev/demo fallback
// ─────────────────────────────────────────────────────────────────────────────

function DemoExplainView() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const expl = useApi(() => getExplanation(sampleId), deps)

  const features: ExplainData[] = useMemo(() => {
    if (!expl.data) return []
    return expl.data.features.map(f => ({ rank: f.rank, feature: f.feature, sensitivity: f.sensitivity }))
  }, [expl.data])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6 }}>
        <Info size={13} color="#3b82f6" />
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
          <strong style={{ color: '#93c5fd' }}>Developer / Demo mode</strong> — Sample #{sampleId}.
        </span>
      </div>
      {expl.error && !expl.loading && <ErrorState error={expl.error} onRetry={expl.refetch} />}
      {expl.loading && <LoadingSkeleton lines={6} height={300} />}
      {features.length > 0 && (
        <ExplainView
          features={features}
          method={expl.data?.method ?? 'feature_ablation_sensitivity'}
          warning={expl.data?.warning ?? 'Sensitivity indicates prediction influence and does not establish causation.'}
        />
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root component
// ─────────────────────────────────────────────────────────────────────────────

export default function Explainability() {
  const { hasAnalysis, isRestoring, restoreStatus } = useAnalysisContext()
  const [demoOpen, setDemoOpen] = useState(false)

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>Explainability</h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Feature sensitivity analysis — which features most influence the model's prediction
        </p>
      </div>

      {/* Causation disclaimer — always visible */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px', background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.22)', borderRadius: 8 }}>
        <AlertTriangle size={16} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />
        <div>
          <div style={{ color: '#f59e0b', fontSize: '0.78rem', fontWeight: 700, marginBottom: 3 }}>Interpretation Warning</div>
          <div style={{ color: '#7d8a6a', fontSize: '0.75rem', lineHeight: 1.5 }}>
            Sensitivity indicates prediction influence and does not establish causation.
            High sensitivity means the model's output changes significantly when a feature is removed —
            it does <strong>not</strong> mean that feature caused the attack.
          </div>
        </div>
      </div>

      {isRestoring && <LoadingSkeleton lines={6} height={300} />}

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
            <AnalysisExplainView />
            <div style={{ borderTop: '1px solid #0f1d33', paddingTop: 8 }}>
              <button onClick={() => setDemoOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', color: '#1e3a5f', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', padding: '4px 0' }}>
                <ChevronDown size={12} style={{ transform: demoOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                Developer / Demo View
              </button>
              {demoOpen && <div style={{ marginTop: 10 }}><DemoExplainView /></div>}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '48px 24px', background: '#0b1526', border: '1px dashed #1a2c4a', borderRadius: 12, textAlign: 'center' }}>
              <UploadCloud size={44} color="#1e3a5f" />
              <div>
                <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>No Analysis Loaded</div>
                <div style={{ color: '#3d5275', fontSize: '0.82rem', maxWidth: 400 }}>Upload network telemetry to view feature sensitivity for the uploaded analysis.</div>
              </div>
              <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
                <UploadCloud size={14} /> Upload Telemetry
              </Link>
            </div>
            <Panel title="Developer / Demo View" subtitle="Pre-built test set — not the primary product view">
              <DemoExplainView />
            </Panel>
          </div>
        )
      )}
    </div>
  )
}
