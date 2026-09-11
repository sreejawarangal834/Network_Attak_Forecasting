/**
 * NetworkState.tsx — Predicted network feature state viewer.
 *
 * PRIMARY MODE  (uploaded analysis in AnalysisContext):
 *   Data source: GET /analysis/{analysis_id}/states
 *   Shows the 44 network-state features for each time-window.
 *   Step selector covers all windows (not just 5).
 *   Labelled NETWORK-LEVEL.
 *
 * FALLBACK MODE (no analysis):
 *   Upload prompt + Developer/Demo section using GET /forecast/{sample_id}/states.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { Search, Info, UploadCloud, ChevronDown } from 'lucide-react'

import { useAnalysisContext } from '../context/AnalysisContext'
import { useSampleContext }   from '../context/SampleContext'
import { useApi }             from '../hooks/useApi'
import { getAnalysisStates, getForecastStates } from '../services/api'
import type { ForecastStateStep, WindowStateOut } from '../types/api'

import Panel          from '../components/Panel'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState     from '../components/ErrorState'

// ─────────────────────────────────────────────────────────────────────────────
// Shared feature viewer (handles both WindowStateOut and ForecastStateStep)
// ─────────────────────────────────────────────────────────────────────────────

interface FeatureViewerProps {
  steps:        Array<{ step: number; label: string; features: Record<string, number> }>
  isNetworkLevel: boolean
}

function FeatureViewer({ steps, isNetworkLevel }: FeatureViewerProps) {
  const [selectedStep, setSelectedStep] = useState(steps[0]?.step ?? 1)
  const [search, setSearch]             = useState('')
  const [topN, setTopN]                 = useState(10)
  const [crossFeature, setCrossFeature] = useState('')

  const currentState = steps.find(s => s.step === selectedStep) ?? steps[0]

  const filteredFeatures = useMemo(() => {
    if (!currentState) return []
    return Object.entries(currentState.features)
      .filter(([name]) => name.toLowerCase().includes(search.toLowerCase()))
      .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
  }, [currentState, search])

  const chartData = filteredFeatures.slice(0, topN).map(([name, value]) => ({
    name:     name.length > 22 ? name.slice(0, 20) + '…' : name,
    fullName: name,
    value:    parseFloat(value.toFixed(4)),
  }))

  const allFeatures = useMemo(() => currentState ? Object.keys(currentState.features).sort() : [], [currentState])
  const initFeature = useMemo(() => allFeatures[0] ?? '', [allFeatures])

  const activeCross = crossFeature || initFeature

  const crossChartData = steps.map(s => ({
    name:  s.label,
    value: parseFloat((s.features[activeCross] ?? 0).toFixed(4)),
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Scope notice */}
      {isNetworkLevel && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6 }}>
          <Info size={13} color="#3b82f6" />
          <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
            <strong style={{ color: '#93c5fd' }}>NETWORK-LEVEL</strong> — these are aggregated 10-second window states for the entire traffic capture.
          </span>
        </div>
      )}

      {/* Step selector */}
      <Panel title="Window / Step">
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {steps.map(s => (
            <button
              key={s.step}
              onClick={() => setSelectedStep(s.step)}
              style={{
                padding: '6px 14px',
                background: selectedStep === s.step ? '#1d4ed8' : '#070d1a',
                border: `1px solid ${selectedStep === s.step ? '#3b82f6' : '#1a2c4a'}`,
                borderRadius: 6, color: selectedStep === s.step ? '#fff' : '#4d6a8a',
                fontSize: '0.75rem', fontWeight: selectedStep === s.step ? 700 : 500,
                cursor: 'pointer',
              }}
            >
              {s.label}
            </button>
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', color: '#3d5275', fontSize: '0.72rem' }}>
            Features: {currentState ? Object.keys(currentState.features).length : '—'}
          </div>
        </div>
      </Panel>

      {/* Chart + table */}
      {currentState && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Panel
            title={`Top ${topN} Feature Values — ${currentState.label}`}
            action={
              <select value={topN} onChange={e => setTopN(Number(e.target.value))} style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 5, color: '#5d7a9a', fontSize: '0.72rem', padding: '3px 6px' }}>
                {[5, 10, 15, 20].map(n => <option key={n} value={n}>Top {n}</option>)}
              </select>
            }
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#3d5275', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fill: '#5d7a9a', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.75rem' }}
                  formatter={(v: unknown, _: unknown, p: { payload?: { fullName: string } }) => [(typeof v === 'number' ? v : 0).toFixed(4), p.payload?.fullName ?? ''] as [string, string]}
                />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel
            title="All Features"
            action={
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Search size={13} color="#3d5275" />
                <input type="text" placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)}
                  style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 5, color: '#e2e8f0', fontSize: '0.75rem', padding: '4px 8px', outline: 'none', width: 130 }} />
              </div>
            }
          >
            <div style={{ height: 260, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0d1526' }}>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '5px 8px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', borderBottom: '1px solid #1a2c4a' }}>Feature</th>
                    <th style={{ textAlign: 'right', padding: '5px 8px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', borderBottom: '1px solid #1a2c4a' }}>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFeatures.map(([name, value], i) => (
                    <tr key={name} style={{ background: i % 2 === 0 ? 'transparent' : '#070d1a' }}>
                      <td style={{ padding: '5px 8px', color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.73rem' }}>{name}</td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', color: '#c8d8ec', fontFamily: 'monospace' }}>{value.toFixed(4)}</td>
                    </tr>
                  ))}
                  {filteredFeatures.length === 0 && (
                    <tr><td colSpan={2} style={{ padding: '20px 8px', textAlign: 'center', color: '#1e3a5f' }}>{search ? `No features match "${search}"` : 'No features.'}</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      {/* Cross-step comparison */}
      {steps.length > 1 && (
        <Panel title="Feature Comparison Across Steps" subtitle="Select a feature to compare its value across all steps">
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#3d5275', fontSize: '0.75rem' }}>Feature:</span>
            <select value={activeCross} onChange={e => setCrossFeature(e.target.value)}
              style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 5, color: '#c8d8ec', fontSize: '0.78rem', padding: '5px 8px', maxWidth: 280 }}>
              {allFeatures.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={crossChartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
              <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
              <YAxis tick={{ fill: '#3d5275', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }} />
              <Bar dataKey="value" fill="#06b6d4" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Primary view — uploaded analysis states
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisStateView() {
  const { analysisId, analysis } = useAnalysisContext()
  const deps   = useMemo(() => [analysisId], [analysisId])
  const result = useApi(() => getAnalysisStates(analysisId!), deps)

  const steps = useMemo((): Array<{ step: number; label: string; features: Record<string, number> }> => {
    if (!result.data) return []
    const raw: WindowStateOut[] = Array.isArray(result.data.states) ? result.data.states : []
    return raw.map((w, i) => ({
      step:     i + 1,
      label:    w.window_start ? `W${i + 1} ${w.window_start.slice(11, 19)}` : `Window ${i + 1}`,
      features: w.features,
    }))
  }, [result.data])

  if (result.loading) return <LoadingSkeleton lines={6} height={300} />
  if (result.error)   return <ErrorState error={result.error} onRetry={result.refetch} />
  if (steps.length === 0) return (
    <div style={{ padding: '32px', textAlign: 'center', color: '#3d5275', background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 8 }}>
      No window states returned for this analysis.
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 7 }}>
        <span style={{ color: '#4ade80', fontSize: '0.78rem', fontWeight: 600 }}>Live Analysis</span>
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem' }}>{analysis?.input.filename}</span>
        <span style={{ color: '#1e3a5f' }}>·</span>
        <span style={{ color: '#2a4060', fontSize: '0.7rem' }}>{steps.length} time windows · {analysis?.input.time_windows} total</span>
      </div>
      <FeatureViewer steps={steps} isNetworkLevel />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Dev/demo fallback — forecast states for a sample
// ─────────────────────────────────────────────────────────────────────────────

function DemoStateView() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps   = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const states = useApi(() => getForecastStates(sampleId), deps)

  const steps = useMemo((): Array<{ step: number; label: string; features: Record<string, number> }> => {
    if (!states.data) return []
    const raw: ForecastStateStep[] = Array.isArray(states.data.states) ? states.data.states : []
    return raw.map(s => ({ step: s.step, label: `Step ${s.step}`, features: s.features }))
  }, [states.data])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6 }}>
        <Info size={13} color="#3b82f6" />
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
          <strong style={{ color: '#93c5fd' }}>Developer / Demo mode</strong> — Sample #{sampleId}, predicted forecast states.
        </span>
      </div>
      {states.error && !states.loading && <ErrorState error={states.error} onRetry={states.refetch} />}
      {states.loading && <LoadingSkeleton lines={5} height={260} />}
      {steps.length > 0 && <FeatureViewer steps={steps} isNetworkLevel={false} />}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root component
// ─────────────────────────────────────────────────────────────────────────────

export default function NetworkState() {
  const { hasAnalysis, isRestoring, restoreStatus } = useAnalysisContext()
  const [demoOpen, setDemoOpen] = useState(false)

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>Network State</h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>44-feature network-state vectors from the uploaded telemetry analysis</p>
      </div>

      {isRestoring && <LoadingSkeleton lines={6} height={260} />}

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
            <AnalysisStateView />
            <div style={{ borderTop: '1px solid #0f1d33', paddingTop: 8 }}>
              <button onClick={() => setDemoOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', color: '#1e3a5f', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', padding: '4px 0' }}>
                <ChevronDown size={12} style={{ transform: demoOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                Developer / Demo View
              </button>
              {demoOpen && <div style={{ marginTop: 10 }}><DemoStateView /></div>}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '48px 24px', background: '#0b1526', border: '1px dashed #1a2c4a', borderRadius: 12, textAlign: 'center' }}>
              <UploadCloud size={44} color="#1e3a5f" />
              <div>
                <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>No Analysis Loaded</div>
                <div style={{ color: '#3d5275', fontSize: '0.82rem', maxWidth: 400 }}>Upload network telemetry to view the 44-feature window states.</div>
              </div>
              <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
                <UploadCloud size={14} /> Upload Telemetry
              </Link>
            </div>
            <Panel title="Developer / Demo View" subtitle="Pre-built test set — forecast states from sample #N">
              <DemoStateView />
            </Panel>
          </div>
        )
      )}
    </div>
  )
}
