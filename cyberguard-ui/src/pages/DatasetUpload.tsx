/**
 * DatasetUpload.tsx — Dataset upload and analysis page.
 *
 * Workflow:
 *   1. User selects/drops a CSV file
 *   2. POST /upload          → validation + upload_id
 *   3. POST /analyze/{id}    → full pipeline (44-feature windowing → inference → forecast)
 *   4. Display AnalysisResponse — current state, 5-step forecast, explainability, optional metrics
 *
 * Supported formats: CSV only (backend limitation — PCAP/PCAPNG not supported).
 * Source/destination IP identifiers: aggregated into feature counts by the pipeline;
 *   individual IPs are NOT preserved in the backend response (backend limitation noted below).
 */

import { useState, useRef, useCallback, useMemo, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import {
  Upload, FileText, AlertTriangle, CheckCircle,
  ChevronRight, Info, Loader, X, RefreshCw, History, Clock,
} from 'lucide-react'

import { uploadFile, analyzeUpload, getAnalysisEntities, getRuns, getRunDetail } from '../services/api'
import type { UploadResponse, AnalysisResponse, UploadForecastStep, RunSummary, RunDetail } from '../types/api'
import { useAnalysisContext } from '../context/AnalysisContext'

import Panel from '../components/Panel'
import StageBadge from '../components/StageBadge'
import MitreBadge from '../components/MitreBadge'
import RiskIndicator from '../components/RiskIndicator'
import ErrorState from '../components/ErrorState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { STAGE_COLORS, fmtPct, fmtPctShort, type AttackStageKey } from '../utils/constants'

// ── Types ─────────────────────────────────────────────────────────────────────

type Phase =
  | 'idle'
  | 'uploading'
  | 'upload_done'
  | 'analyzing'
  | 'done'
  | 'error'

const MAX_SIZE_BYTES = 50 * 1024 * 1024  // 50 MB — matches backend

function fmtBytes(b: number) {
  if (b < 1024)           return `${b} B`
  if (b < 1024 * 1024)    return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

// ── Drop-zone ─────────────────────────────────────────────────────────────────

function DropZone({
  onFile, disabled,
}: { onFile: (f: File) => void; disabled: boolean }) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false)
    if (disabled) return
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }, [onFile, disabled])

  const border = dragging ? '#3b82f6' : '#1a2c4a'
  const bg     = dragging ? 'rgba(59,130,246,0.06)' : '#0b1526'

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      style={{
        border: `2px dashed ${border}`,
        borderRadius: 10, background: bg,
        padding: '36px 24px', textAlign: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s', opacity: disabled ? 0.5 : 1,
      }}
    >
      <input
        ref={inputRef} type="file" accept=".csv"
        style={{ display: 'none' }}
        onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f) }}
        disabled={disabled}
      />
      <Upload size={32} color={dragging ? '#3b82f6' : '#1e3a5f'} style={{ margin: '0 auto 12px' }} />
      <div style={{ color: '#c8d8ec', fontSize: '0.9rem', fontWeight: 600, marginBottom: 6 }}>
        {dragging ? 'Drop file here' : 'Drag & drop or click to select'}
      </div>
      <div style={{ color: '#3d5275', fontSize: '0.78rem', marginBottom: 12 }}>
        Accepted format: <strong style={{ color: '#5d7a9a' }}>.csv</strong>
        {' '}— Packet telemetry or Flow telemetry
      </div>
      <div style={{
        display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap',
      }}>
        {[
          { fmt: 'CSV', note: 'Supported', color: '#22c55e' },
          { fmt: 'PCAP', note: 'Not supported', color: '#ef444488' },
          { fmt: 'PCAPNG', note: 'Not supported', color: '#ef444488' },
        ].map(({ fmt, note, color }) => (
          <span key={fmt} style={{
            background: '#111e35', border: `1px solid ${color}33`,
            borderRadius: 5, padding: '2px 10px',
            color, fontSize: '0.7rem',
          }}>
            {fmt} — {note}
          </span>
        ))}
      </div>
      <div style={{ color: '#1e3a5f', fontSize: '0.68rem', marginTop: 10 }}>
        Max file size: {fmtBytes(MAX_SIZE_BYTES)}
      </div>
    </div>
  )
}

// ── File info strip ───────────────────────────────────────────────────────────

function FileStrip({
  file, onClear,
}: { file: File; onClear: () => void }) {
  const ok = file.size <= MAX_SIZE_BYTES && file.name.endsWith('.csv')
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 14px',
      background: ok ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
      border: `1px solid ${ok ? '#22c55e33' : '#ef444433'}`,
      borderRadius: 7,
    }}>
      <FileText size={16} color={ok ? '#22c55e' : '#ef4444'} />
      <div style={{ flex: 1 }}>
        <div style={{ color: '#c8d8ec', fontSize: '0.82rem', fontWeight: 600 }}>
          {file.name}
        </div>
        <div style={{ color: '#3d5275', fontSize: '0.7rem' }}>
          {fmtBytes(file.size)}
          {!file.name.endsWith('.csv') && (
            <span style={{ color: '#ef4444', marginLeft: 8 }}>
              ✕ Only .csv accepted
            </span>
          )}
          {file.size > MAX_SIZE_BYTES && (
            <span style={{ color: '#ef4444', marginLeft: 8 }}>
              ✕ Exceeds {fmtBytes(MAX_SIZE_BYTES)} limit
            </span>
          )}
        </div>
      </div>
      <button onClick={onClear} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        color: '#3d5275', padding: 4,
      }}>
        <X size={14} />
      </button>
    </div>
  )
}

// ── Phase progress indicator ──────────────────────────────────────────────────

function PhaseBar({ phase }: { phase: Phase }) {
  const steps = [
    { key: 'uploading',    label: 'Upload' },
    { key: 'upload_done',  label: 'Validate' },
    { key: 'analyzing',    label: 'Pipeline' },
    { key: 'done',         label: 'Complete' },
  ]
  const ORDER: Record<string, number> = {
    idle: -1, uploading: 0, upload_done: 1, analyzing: 2, done: 3, error: 3,
  }
  const cur = ORDER[phase] ?? -1

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
      {steps.map((s, i) => {
        const idx   = ORDER[s.key]
        const done  = cur > idx
        const active = cur === idx
        const color  = done ? '#22c55e' : active ? '#3b82f6' : '#1a2c4a'

        return (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
            <div style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              flex: 1,
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: done ? '#22c55e18' : active ? '#3b82f618' : '#111e35',
                border: `2px solid ${color}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {done
                  ? <CheckCircle size={14} color="#22c55e" />
                  : active
                    ? <Loader size={14} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
                    : <span style={{ color: '#1e3a5f', fontSize: '0.7rem' }}>{i + 1}</span>
                }
              </div>
              <span style={{ color, fontSize: '0.65rem', fontWeight: 600 }}>{s.label}</span>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                height: 2, flex: 0.5,
                background: cur > idx ? '#22c55e44' : '#1a2c4a',
                margin: '0 2px', marginBottom: 20,
              }} />
            )}
          </div>
        )
      })}
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

// ── Upload result card ────────────────────────────────────────────────────────

function UploadResultCard({ result }: { result: UploadResponse }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12,
    }}>
      {[
        { label: 'Rows',       value: result.rows.toLocaleString() },
        { label: 'File Type',  value: result.file_type ?? 'unknown' },
        { label: 'Size',       value: fmtBytes(result.size_bytes) },
        { label: 'Labels',     value: result.has_labels ? 'Present' : 'Not found' },
      ].map(({ label, value }) => (
        <div key={label} style={{
          background: '#070d1a', border: '1px solid #1a2c4a',
          borderRadius: 7, padding: '10px 14px',
        }}>
          <div style={{ color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            {label}
          </div>
          <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginTop: 4 }}>
            {value}
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Forecast steps ────────────────────────────────────────────────────────────

function ForecastStepCard({ step }: { step: UploadForecastStep }) {
  const c = STAGE_COLORS[step.stage as AttackStageKey] ?? '#7d95b5'
  return (
    <div style={{
      background: '#070d1a', border: `1px solid ${c}33`,
      borderTop: `2px solid ${c}`, borderRadius: 8, padding: '12px 14px',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ color: '#3d5275', fontSize: '0.65rem', fontWeight: 700 }}>
          STEP {step.step}
        </span>
        <span style={{
          color: step.risk === 'CRITICAL' ? '#7c3aed'
               : step.risk === 'HIGH'     ? '#ef4444'
               : step.risk === 'MEDIUM'   ? '#f59e0b' : '#22c55e',
          fontSize: '0.65rem', fontWeight: 700,
        }}>
          {step.risk}
        </span>
      </div>
      <StageBadge stage={step.stage} size="sm" />
      <div style={{ color: c, fontSize: '1rem', fontWeight: 800 }}>
        {fmtPctShort(step.attack_probability)}
      </div>
      <div style={{ color: '#2a4060', fontSize: '0.65rem' }}>
        conf: {fmtPctShort(step.stage_confidence)}
      </div>
      {step.mitre_attack_id && (
        <MitreBadge id={step.mitre_attack_id} name={step.mitre_attack_name ?? ''} size="sm" />
      )}
    </div>
  )
}

// ── Analysis result ───────────────────────────────────────────────────────────

function AnalysisResult({ result }: { result: AnalysisResponse }) {
  const { current_state: cs, forecast, explainability, metrics, input } = result

  // Forecast probability chart
  const chartData = useMemo(() =>
    forecast.map(f => ({ name: `Step ${f.step}`, prob: f.attack_probability })),
  [forecast])

  // Explainability bars
  const maxSens = explainability[0]?.sensitivity ?? 1
  const topFeats = explainability.slice(0, 10)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Input summary */}
      <Panel title="Telemetry Summary" subtitle="Derived from uploaded file after windowing">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
          {[
            { label: 'Records',      value: input.records.toLocaleString() },
            { label: 'Time Windows', value: input.time_windows.toLocaleString() },
            { label: 'Start',        value: input.ts_start },
            { label: 'End',          value: input.ts_end },
            { label: 'Schema',       value: input.file_type },
          ].map(({ label, value }) => (
            <div key={label} style={{
              background: '#070d1a', border: '1px solid #1a2c4a',
              borderRadius: 6, padding: '8px 12px',
            }}>
              <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
                {label}
              </div>
              <div style={{ color: '#c8d8ec', fontSize: '0.82rem', fontWeight: 600, marginTop: 3, wordBreak: 'break-all' }}>
                {value}
              </div>
            </div>
          ))}
        </div>

        {/* Device identifier limitation notice */}
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 7,
          marginTop: 12, padding: '8px 12px',
          background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.18)',
          borderRadius: 6, color: '#92795a', fontSize: '0.72rem',
        }}>
          <Info size={13} style={{ marginTop: 1, flexShrink: 0, color: '#f59e0b' }} />
          <span>
            <strong style={{ color: '#f59e0b' }}>Device/IP identifiers:</strong>{' '}
            Source and destination IP addresses from your file are aggregated into
            feature counts (e.g. <code>packet_unique_src_ips</code>) during windowing.
            Individual host identifiers are not preserved in the analysis result.
            This is a current backend limitation.
          </span>
        </div>
      </Panel>

      {/* Current state + risk */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <Panel title="Current State — Most Recent Window">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <StageBadge stage={cs.stage} size="lg" />
              <span style={{
                background: `${STAGE_COLORS[cs.stage as AttackStageKey] ?? '#3b82f6'}18`,
                border: `1px solid ${STAGE_COLORS[cs.stage as AttackStageKey] ?? '#3b82f6'}44`,
                borderRadius: 4, padding: '2px 8px',
                color: '#5d7a9a', fontSize: '0.68rem',
              }}>
                {cs.risk}
              </span>
            </div>
            <RiskIndicator probability={cs.attack_probability} size="md" />
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#3d5275', fontSize: '0.75rem' }}>Stage Confidence</span>
              <span style={{ color: '#7d95b5', fontWeight: 600 }}>
                {fmtPct(cs.stage_confidence)}
              </span>
            </div>
            {cs.mitre_attack_id && (
              <MitreBadge id={cs.mitre_attack_id} name={cs.mitre_attack_name ?? ''} />
            )}
            <div style={{ color: '#1e3a5f', fontSize: '0.65rem', marginTop: 4 }}>
              Representative MITRE ATT&amp;CK mapping — prototype stage-to-technique assignment.
            </div>
          </div>
        </Panel>

        {/* Metrics (if labels present) */}
        <Panel
          title="Evaluation Metrics"
          subtitle={metrics ? "Labels detected — performance against ground truth" : "No ground-truth labels in uploaded file"}
        >
          {metrics ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { label: 'Attack Accuracy',  v: metrics.attack_accuracy },
                { label: 'Attack Precision', v: metrics.attack_precision },
                { label: 'Attack Recall',    v: metrics.attack_recall },
                { label: 'Attack F1',        v: metrics.attack_f1 },
              ].map(({ label, v }) => (
                <div key={label} style={{
                  background: '#070d1a', border: '1px solid #1a2c4a',
                  borderRadius: 6, padding: '8px 12px',
                }}>
                  <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>
                    {label}
                  </div>
                  <div style={{
                    color: '#3b82f6', fontSize: '1.1rem',
                    fontWeight: 800, marginTop: 4,
                  }}>
                    {v != null ? fmtPct(v) : 'N/A'}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: '#2a4060', fontSize: '0.82rem', padding: '12px 0' }}>
              Include a <code>label</code>, <code>attack_type</code>, or <code>attack_stage</code>
              {' '}column in your CSV to enable evaluation metrics.
            </div>
          )}
        </Panel>
      </div>

      {/* 5-step forecast */}
      <Panel
        title="5-Step Autoregressive Forecast"
        subtitle="Predicted states fed back into the model — ground truth not used"
      >
        <div style={{ display: 'flex', alignItems: 'stretch', gap: 8, marginBottom: 16 }}>
          {forecast.map((step, i) => (
            <div key={step.step} style={{ flex: 1, display: 'flex', alignItems: 'stretch', gap: 8 }}>
              <ForecastStepCard step={step} />
              {i < forecast.length - 1 && (
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <ChevronRight size={14} color="#1e3a5f" />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Probability chart */}
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id="uploadRiskGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#ef4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
            <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 10 }} />
            <YAxis
              domain={[0, 1]} tickFormatter={v => `${(v as number * 100).toFixed(0)}%`}
              tick={{ fill: '#3d5275', fontSize: 10 }}
            />
            <Tooltip
              contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
              formatter={(v: unknown) => [fmtPct(typeof v === 'number' ? v : 0), 'Attack Probability']}
            />
            <Area type="monotone" dataKey="prob" stroke="#ef4444" strokeWidth={2}
              fill="url(#uploadRiskGrad)" dot={{ fill: '#ef4444', r: 4, strokeWidth: 0 }} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>

      {/* Explainability */}
      <Panel
        title="Feature Sensitivity — Top 10"
        subtitle="Prediction influence; does not imply causation"
      >
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 8,
          marginBottom: 12, padding: '8px 12px',
          background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.18)',
          borderRadius: 6,
        }}>
          <AlertTriangle size={13} color="#f59e0b" style={{ marginTop: 2, flexShrink: 0 }} />
          <span style={{ color: '#927a5a', fontSize: '0.72rem' }}>
            Sensitivity indicates how much the model's prediction changes when a feature is removed.
            It quantifies prediction influence — <strong>not causal attribution</strong>.
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {topFeats.map((f, i) => {
            const rel = f.sensitivity / maxSens
            const colors = ['#ef4444','#f97316','#f59e0b','#eab308','#84cc16',
                            '#22c55e','#06b6d4','#3b82f6','#8b5cf6','#7d95b5']
            const c = colors[Math.min(i, colors.length - 1)]
            return (
              <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ color: '#1e3a5f', fontSize: '0.65rem', width: 18, textAlign: 'right', flexShrink: 0 }}>
                  #{i + 1}
                </span>
                <span style={{ color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.75rem', width: 200, flexShrink: 0 }}>
                  {f.feature}
                </span>
                <div style={{ flex: 1, height: 6, background: '#111e35', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${rel * 100}%`, background: c, borderRadius: 3 }} />
                </div>
                <span style={{ color: c, fontSize: '0.72rem', fontFamily: 'monospace', width: 62, textAlign: 'right', flexShrink: 0 }}>
                  {f.sensitivity.toFixed(5)}
                </span>
              </div>
            )
          })}
        </div>
      </Panel>
    </div>
  )
}

// ── Main page component ───────────────────────────────────────────────────────

export default function DatasetUpload() {
  const [file,         setFile]         = useState<File | null>(null)
  const [phase,        setPhase]        = useState<Phase>('idle')
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null)
  const [analysis,     setAnalysis]     = useState<AnalysisResponse | null>(null)
  const [error,        setError]        = useState<string | null>(null)
  const [statusMsg,    setStatusMsg]    = useState('')

  // Global analysis context — populated so Dashboard can consume it
  const ctx = useAnalysisContext()

  function reset() {
    setFile(null); setPhase('idle'); setUploadResult(null)
    setAnalysis(null); setError(null); setStatusMsg('')
    ctx.resetAnalysis()
  }

  async function handleRun() {
    if (!file) return
    setError(null); setAnalysis(null); setUploadResult(null)
    ctx.setAnalysisError(null)

    // ── Step 1: upload ────────────────────────────────────────
    setPhase('uploading')
    ctx.setAnalysisLoading(true)
    setStatusMsg('Uploading and validating file…')
    let upResult: UploadResponse
    try {
      upResult = await uploadFile(file)
      setUploadResult(upResult)
      setPhase('upload_done')
      setStatusMsg(`Validated — ${upResult.rows.toLocaleString()} records (${upResult.file_type} schema). Running analysis…`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed'
      setError(msg)
      ctx.setAnalysisError(msg)
      ctx.setAnalysisLoading(false)
      setPhase('error')
      return
    }

    // ── Step 2: analyze ───────────────────────────────────────
    setPhase('analyzing')
    try {
      const result = await analyzeUpload(upResult.upload_id)
      setAnalysis(result)
      ctx.setAnalysis(result)
      setPhase('done')
      setStatusMsg('Analysis complete. Fetching entity data…')

      // ── Step 3: fetch entities (best-effort — non-blocking) ──
      try {
        const entities = await getAnalysisEntities(result.analysis_id)
        ctx.setEntitiesData(entities)
        const count = entities.total_entities
        const label = entities.has_entity_ids
          ? `${count} device${count !== 1 ? 's' : ''} identified`
          : 'Network-level prediction (no IP identifiers in file)'
        setStatusMsg(`Analysis complete — ${label}. View the Dashboard for results.`)
      } catch {
        // Entity fetch is non-critical — analysis result still shown
        setStatusMsg('Analysis complete. View the Dashboard for results.')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Analysis failed'
      setError(msg)
      ctx.setAnalysisError(msg)
      setPhase('error')
    } finally {
      ctx.setAnalysisLoading(false)
    }
  }

  const canRun = file !== null
    && file.name.endsWith('.csv')
    && file.size <= MAX_SIZE_BYTES
    && phase !== 'uploading'
    && phase !== 'analyzing'

  const busy = phase === 'uploading' || phase === 'analyzing'

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Page header */}
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Dataset Upload
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Upload CSV telemetry → pipeline builds 44-feature windows → World Model inference + 5-step forecast
        </p>
      </div>

      {/* Workflow comparison */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12,
      }}>
        {[
          {
            label: 'Demo workflow (existing)',
            flow:  'Sample index → pre-computed test set → prediction',
            color: '#3b82f6',
          },
          {
            label: 'Upload workflow (this page)',
            flow:  'Your CSV → telemetry pipeline → windowing → inference → forecast',
            color: '#06b6d4',
          },
        ].map(({ label, flow, color }) => (
          <div key={label} style={{
            background: '#0b1526', border: `1px solid ${color}33`,
            borderLeft: `3px solid ${color}`, borderRadius: 7,
            padding: '10px 14px',
          }}>
            <div style={{ color, fontSize: '0.72rem', fontWeight: 700, marginBottom: 4 }}>
              {label}
            </div>
            <div style={{ color: '#3d5275', fontSize: '0.75rem' }}>{flow}</div>
          </div>
        ))}
      </div>

      {/* Upload panel */}
      <Panel title="Upload Telemetry File">
        <DropZone onFile={f => { reset(); setFile(f) }} disabled={busy} />

        {file && (
          <div style={{ marginTop: 12 }}>
            <FileStrip file={file} onClear={reset} />
          </div>
        )}

        {/* Progress */}
        {phase !== 'idle' && (
          <div style={{ marginTop: 16 }}>
            <PhaseBar phase={phase} />
          </div>
        )}

        {/* Status message */}
        {statusMsg && phase !== 'error' && (
          <div style={{
            marginTop: 12, padding: '8px 12px',
            background: 'rgba(59,130,246,0.06)',
            border: '1px solid rgba(59,130,246,0.18)',
            borderRadius: 6, color: '#5d7a9a', fontSize: '0.78rem',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            {busy && <Loader size={13} style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />}
            {!busy && phase === 'done' && <CheckCircle size={13} color="#22c55e" />}
            {statusMsg}
          </div>
        )}

        {/* Error */}
        {error && phase === 'error' && (
          <div style={{ marginTop: 12 }}>
            <ErrorState error={error} onRetry={handleRun} compact />
          </div>
        )}

        {/* Action buttons */}
        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
          <button
            onClick={handleRun}
            disabled={!canRun}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 20px',
              background: canRun ? '#1d4ed8' : '#111e35',
              border: `1px solid ${canRun ? '#3b82f6' : '#1a2c4a'}`,
              borderRadius: 6, color: canRun ? '#fff' : '#3d5275',
              fontSize: '0.82rem', fontWeight: 600,
              cursor: canRun ? 'pointer' : 'not-allowed',
              opacity: busy ? 0.7 : 1,
            }}
          >
            {busy
              ? <><Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> Processing…</>
              : <><Upload size={14} /> Analyse File</>
            }
          </button>

          {phase === 'done' && (
            <Link to="/" style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 18px',
              background: 'rgba(34,197,94,0.10)',
              border: '1px solid rgba(34,197,94,0.35)',
              borderRadius: 6, color: '#4ade80',
              fontSize: '0.82rem', fontWeight: 600,
              textDecoration: 'none', cursor: 'pointer',
            }}>
              <CheckCircle size={14} /> View Dashboard
            </Link>
          )}

          {(phase === 'done' || phase === 'error') && (
            <button onClick={reset} style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 16px',
              background: '#0b1526', border: '1px solid #1a2c4a',
              borderRadius: 6, color: '#5d7a9a',
              fontSize: '0.82rem', cursor: 'pointer',
            }}>
              <RefreshCw size={13} /> Upload another file
            </button>
          )}
        </div>
      </Panel>

      {/* Upload result summary */}
      {uploadResult && (
        <Panel title="Validation Result" subtitle={`upload_id: ${uploadResult.upload_id}`}>
          <UploadResultCard result={uploadResult} />
        </Panel>
      )}

      {/* Analysis in progress skeleton */}
      {phase === 'analyzing' && !analysis && (
        <Panel title="Running Analysis…">
          <LoadingSkeleton lines={6} height={200} />
          <div style={{ color: '#2a4060', fontSize: '0.78rem', marginTop: 12 }}>
            Building time windows · Running inference · Autoregressive rollout · Feature sensitivity…
          </div>
        </Panel>
      )}

      {/* Full analysis result */}
      {analysis && phase === 'done' && (
        <AnalysisResult result={analysis} />
      )}

      {/* Prediction run history — always shown, sourced from SQLite */}
      <RunHistory />
    </div>
  )
}

// ── RunHistory ────────────────────────────────────────────────────────────────
// Shows previous prediction runs from SQLite (GET /runs).
// Survives backend restarts — data is persisted to disk.
// Selecting a run loads its full detail and optionally restores it to
// AnalysisContext so the Dashboard reflects it.

function riskColor(r: string) {
  if (r === 'CRITICAL') return '#7c3aed'
  if (r === 'HIGH')     return '#ef4444'
  if (r === 'MEDIUM')   return '#f59e0b'
  return '#22c55e'
}

function fmtShortDate(iso: string) {
  // "2026-09-09 10:23:45 UTC" → "Sep 9, 10:23"
  try {
    const d = new Date(iso.replace(' UTC', 'Z'))
    return d.toLocaleString([], {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso.slice(0, 16) }
}

interface RunRowProps {
  run:        RunSummary
  isSelected: boolean
  onSelect:   (id: string) => void
}

function RunRow({ run, isSelected, onSelect }: RunRowProps) {
  const rc = riskColor(run.risk_level)
  return (
    <button
      onClick={() => onSelect(run.run_id)}
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto auto auto',
        alignItems: 'center', gap: 12,
        width: '100%', padding: '10px 14px',
        background: isSelected ? '#0f1d33' : '#070d1a',
        border: `1px solid ${isSelected ? '#3b82f6' : '#1a2c4a'}`,
        borderLeft: `3px solid ${isSelected ? '#3b82f6' : rc}`,
        borderRadius: 7, cursor: 'pointer', textAlign: 'left',
        transition: 'all 0.15s',
      }}
    >
      {/* Filename + timestamp */}
      <div style={{ minWidth: 0 }}>
        <div style={{
          color: '#c8d8ec', fontSize: '0.8rem', fontWeight: isSelected ? 700 : 500,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          fontFamily: 'monospace',
        }}>
          {run.filename ?? `sample run`}
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          color: '#3d5275', fontSize: '0.65rem', marginTop: 2,
        }}>
          <Clock size={10} />
          {fmtShortDate(run.created_at)}
          {run.total_records != null && (
            <span style={{ color: '#2a4060' }}>· {run.total_records.toLocaleString()} rows</span>
          )}
          {run.file_type && (
            <span style={{
              background: '#111e35', border: '1px solid #1a2c4a',
              borderRadius: 3, padding: '0 5px',
              color: '#3d5275', fontSize: '0.6rem',
            }}>
              {run.file_type}
            </span>
          )}
        </div>
      </div>

      {/* Stage */}
      <div style={{
        color: STAGE_COLORS[run.predicted_stage as AttackStageKey] ?? '#7d95b5',
        fontSize: '0.72rem', fontWeight: 600, flexShrink: 0,
      }}>
        {run.predicted_stage}
      </div>

      {/* Probability */}
      <div style={{ color: rc, fontSize: '0.8rem', fontWeight: 800, flexShrink: 0 }}>
        {(run.attack_probability * 100).toFixed(1)}%
      </div>

      {/* Risk badge */}
      <span style={{
        background: `${rc}18`, border: `1px solid ${rc}44`,
        borderRadius: 4, padding: '2px 7px',
        color: rc, fontSize: '0.65rem', fontWeight: 700, flexShrink: 0,
      }}>
        {run.risk_level}
      </span>
    </button>
  )
}

function RunDetailPanel({ detail }: { detail: RunDetail }) {
  const rc = riskColor(detail.risk_level)
  const maxSens = detail.explainability[0]?.sensitivity ?? 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Summary strip */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
      }}>
        {[
          { label: 'Stage',       value: detail.predicted_stage,  color: STAGE_COLORS[detail.predicted_stage as AttackStageKey] ?? '#7d95b5' },
          { label: 'Probability', value: `${(detail.attack_probability * 100).toFixed(2)}%`, color: rc },
          { label: 'Risk',        value: detail.risk_level,        color: rc },
          { label: 'Confidence',  value: `${(detail.stage_confidence * 100).toFixed(1)}%`,  color: '#7d95b5' },
        ].map(({ label, value, color }) => (
          <div key={label} style={{
            background: '#070d1a', border: '1px solid #1a2c4a',
            borderRadius: 6, padding: '8px 10px',
          }}>
            <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase' }}>{label}</div>
            <div style={{ color, fontSize: '0.88rem', fontWeight: 700, marginTop: 3 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Forecast steps */}
      {detail.forecast.length > 0 && (
        <Panel title="5-Step Forecast" subtitle="From stored run — autoregressive, ground truth not used">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            {detail.forecast.map((f, i) => {
              const c = STAGE_COLORS[f.predicted_stage as AttackStageKey] ?? '#7d95b5'
              return (
                <div key={f.step} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{
                    background: `${c}10`, border: `1px solid ${c}33`,
                    borderRadius: 7, padding: '7px 12px', textAlign: 'center',
                  }}>
                    <div style={{ color: '#3d5275', fontSize: '0.6rem', marginBottom: 3 }}>+{f.step * 10}s</div>
                    <div style={{ color: c, fontSize: '0.78rem', fontWeight: 700 }}>{f.predicted_stage}</div>
                    <div style={{ color: c, fontSize: '0.82rem', fontWeight: 800 }}>
                      {(f.attack_probability * 100).toFixed(1)}%
                    </div>
                  </div>
                  {i < detail.forecast.length - 1 && <ChevronRight size={12} color="#1e3a5f" />}
                </div>
              )
            })}
          </div>
        </Panel>
      )}

      {/* Top features */}
      {detail.explainability.length > 0 && (
        <Panel title="Top Evidence Features" subtitle="Feature ablation sensitivity — prediction influence, not causation">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {detail.explainability.slice(0, 5).map((f, i) => {
              const rel = f.sensitivity / maxSens
              const colors = ['#ef4444','#f97316','#f59e0b','#eab308','#84cc16']
              const c = colors[i] ?? '#7d95b5'
              return (
                <div key={f.feature_name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ color: '#1e3a5f', fontSize: '0.62rem', width: 16, textAlign: 'right', flexShrink: 0 }}>
                    #{f.rank}
                  </span>
                  <span style={{
                    color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.72rem',
                    width: 210, flexShrink: 0,
                  }}>
                    {f.feature_name}
                  </span>
                  <div style={{ flex: 1, height: 5, background: '#111e35', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${rel * 100}%`, background: c, borderRadius: 3 }} />
                  </div>
                  <span style={{ color: c, fontSize: '0.68rem', fontFamily: 'monospace', width: 58, textAlign: 'right', flexShrink: 0 }}>
                    {f.sensitivity.toFixed(5)}
                  </span>
                </div>
              )
            })}
          </div>
        </Panel>
      )}
    </div>
  )
}

function RunHistory() {
  const [runs,         setRuns]         = useState<RunSummary[]>([])
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState<string | null>(null)
  const [selectedId,   setSelectedId]   = useState<string | null>(null)
  const [detail,       setDetail]       = useState<RunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError,  setDetailError]  = useState<string | null>(null)

  const ctx = useAnalysisContext()

  // Fetch run list on mount and after a new analysis completes
  const fetchRuns = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const rows = await getRuns(50)
      setRuns(rows)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load run history')
    } finally {
      setLoading(false)
    }
  }, [])

  // Refresh the list whenever the active analysis changes (new upload completed)
  useEffect(() => { fetchRuns() }, [fetchRuns, ctx.analysisId])

  const handleSelect = useCallback(async (runId: string) => {
    if (runId === selectedId) {
      // Deselect
      setSelectedId(null); setDetail(null); setDetailError(null)
      return
    }
    setSelectedId(runId); setDetail(null); setDetailError(null); setDetailLoading(true)
    try {
      const d = await getRunDetail(runId)
      setDetail(d)
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : 'Failed to load run detail')
    } finally {
      setDetailLoading(false)
    }
  }, [selectedId])

  if (loading) {
    return (
      <Panel title="Prediction History" subtitle="Previous runs from SQLite — survives backend restarts">
        <div style={{ color: '#2a4060', fontSize: '0.78rem', padding: '8px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Loading run history…
          <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
        </div>
      </Panel>
    )
  }

  if (error) {
    return (
      <Panel title="Prediction History">
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0',
          color: '#ef4444', fontSize: '0.78rem',
        }}>
          <AlertTriangle size={13} /> {error}
          <button onClick={fetchRuns} style={{
            marginLeft: 8, background: 'none', border: '1px solid #1a2c4a',
            borderRadius: 5, color: '#5d7a9a', fontSize: '0.72rem',
            padding: '3px 10px', cursor: 'pointer',
          }}>
            Retry
          </button>
        </div>
      </Panel>
    )
  }

  if (runs.length === 0) {
    return (
      <Panel
        title="Prediction History"
        subtitle="Runs are stored in SQLite and survive backend restarts"
      >
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          color: '#2a4060', fontSize: '0.78rem', padding: '8px 0',
        }}>
          <History size={13} />
          No prediction runs stored yet. Upload and analyse a file to create the first record.
        </div>
      </Panel>
    )
  }

  return (
    <Panel
      title={`Prediction History — ${runs.length} run${runs.length !== 1 ? 's' : ''}`}
      subtitle="Stored in SQLite · persists across backend restarts · click a row to expand"
      action={
        <button
          onClick={fetchRuns}
          title="Refresh run list"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#3d5275', fontSize: '0.72rem', display: 'flex',
            alignItems: 'center', gap: 4,
          }}
        >
          <RefreshCw size={11} /> Refresh
        </button>
      }
    >
      {/* Column header */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr auto auto auto',
        gap: 12, padding: '0 14px 6px',
        color: '#1e3a5f', fontSize: '0.6rem', fontWeight: 700,
        textTransform: 'uppercase', letterSpacing: '0.08em',
        borderBottom: '1px solid #0f1d33', marginBottom: 6,
      }}>
        <span>File / Timestamp</span>
        <span>Stage</span>
        <span>Prob.</span>
        <span>Risk</span>
      </div>

      {/* Run rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 320, overflowY: 'auto' }}>
        {runs.map(run => (
          <RunRow
            key={run.run_id}
            run={run}
            isSelected={run.run_id === selectedId}
            onSelect={handleSelect}
          />
        ))}
      </div>

      {/* Detail panel for selected run */}
      {selectedId && (
        <div style={{ marginTop: 14 }}>
          {detailLoading && (
            <div style={{ color: '#2a4060', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Loading details…
            </div>
          )}
          {detailError && (
            <div style={{ color: '#ef4444', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertTriangle size={13} /> {detailError}
            </div>
          )}
          {detail && !detailLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Header + "Load to Dashboard" button */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                flexWrap: 'wrap', gap: 8,
                padding: '8px 14px',
                background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.2)',
                borderRadius: 7,
              }}>
                <div>
                  <div style={{ color: '#93c5fd', fontSize: '0.75rem', fontWeight: 700 }}>
                    Run details
                  </div>
                  <div style={{
                    color: '#2a4060', fontFamily: 'monospace', fontSize: '0.65rem', marginTop: 2,
                  }}>
                    {detail.run_id}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Link
                    to="/"
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '5px 14px',
                      background: 'rgba(34,197,94,0.10)',
                      border: '1px solid rgba(34,197,94,0.3)',
                      borderRadius: 5, color: '#4ade80',
                      fontSize: '0.72rem', fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    <CheckCircle size={11} /> View on Dashboard
                  </Link>
                </div>
              </div>
              <RunDetailPanel detail={detail} />
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}
