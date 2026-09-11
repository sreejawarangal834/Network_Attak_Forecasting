/**
 * SystemStatus.tsx — API + model health + alert configuration page.
 *
 * Consumes:
 *   GET  /health
 *   GET  /model/info
 *   GET  /alerts/status
 *   POST /alerts/test
 */

import { useEffect, useState } from 'react'
import {
  Activity, Cpu, Layers, Hash, GitBranch, Server,
  Mail, CheckCircle, XCircle, Send, Loader,
  FileText, Monitor, AlertTriangle, UploadCloud,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { getHealth, getModelInfo, getAlertStatus, testAlert } from '../services/api'
import { useAnalysisContext } from '../context/AnalysisContext'
import type {
  HealthResponse, ModelInfoResponse,
  AlertStatusResponse, AlertTestResponse,
} from '../types/api'

import Panel from '../components/Panel'
import MetricCard from '../components/MetricCard'
import LoadingSkeleton, { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

// ── Analysis status panel ──────────────────────────────────────────────────

function AnalysisStatusPanel() {
  const {
    hasAnalysis, analysis, analysisId, analysisLabel,
    analysisLoading, analysisError,
    entitiesData, selectedEntity, resetAnalysis,
  } = useAnalysisContext()

  const cs           = analysis?.current_state
  const input        = analysis?.input
  const hasEntityIds = entitiesData?.has_entity_ids  ?? false
  const totalEnts    = entitiesData?.total_entities   ?? 0
  const highRisk     = entitiesData?.high_risk_count  ?? 0
  const netRisk      = entitiesData?.network_prediction?.risk ?? null

  const riskColor = (r: string | null) =>
    r === 'CRITICAL' ? '#7c3aed'
    : r === 'HIGH'   ? '#ef4444'
    : r === 'MEDIUM' ? '#f59e0b'
    : r === 'LOW'    ? '#22c55e'
    : '#3d5275'

  return (
    <Panel
      title="Current Analysis"
      subtitle="Status of the most recently uploaded and analysed telemetry file"
    >
      {analysisLoading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0' }}>
          <Loader size={16} color="#3b82f6" style={{ animation: 'spin 1s linear infinite' }} />
          <span style={{ color: '#5d7a9a', fontSize: '0.82rem' }}>Analysis in progress…</span>
          <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
        </div>
      ) : analysisError ? (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 14px',
          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
          borderRadius: 7, color: '#f87171', fontSize: '0.78rem',
        }}>
          <XCircle size={14} />
          Last analysis failed: {analysisError}
        </div>
      ) : !hasAnalysis ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 10 }}>
          <div style={{ color: '#2a4060', fontSize: '0.82rem' }}>
            No analysis loaded. Upload a CSV telemetry file to begin.
          </div>
          <Link to="/upload" style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '7px 16px',
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.25)',
            borderRadius: 6, color: '#3b82f6',
            fontSize: '0.78rem', fontWeight: 600,
            textDecoration: 'none',
          }}>
            <UploadCloud size={13} /> Upload Telemetry File
          </Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* File + analysis ID */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10,
          }}>
            {[
              {
                icon: <FileText size={13} color="#22c55e" />,
                label: 'Filename',
                value: analysisLabel,
                mono: true,
              },
              {
                icon: <Activity size={13} color="#3b82f6" />,
                label: 'Analysis ID',
                value: analysisId ?? '—',
                mono: true,
              },
              {
                icon: <Activity size={13} color="#5d7a9a" />,
                label: 'Records',
                value: input?.records.toLocaleString() ?? '—',
                mono: false,
              },
              {
                icon: <Activity size={13} color="#5d7a9a" />,
                label: 'Time Windows',
                value: input?.time_windows.toLocaleString() ?? '—',
                mono: false,
              },
              {
                icon: <Activity size={13} color="#5d7a9a" />,
                label: 'Schema',
                value: input?.file_type ?? '—',
                mono: true,
              },
              {
                icon: <Activity size={13} color="#5d7a9a" />,
                label: 'Time Range',
                value: input ? `${input.ts_start.slice(0, 19)} → ${input.ts_end.slice(0, 19)}` : '—',
                mono: true,
              },
            ].map(({ icon, label, value, mono }) => (
              <div key={label} style={{
                background: '#070d1a', border: '1px solid #1a2c4a',
                borderRadius: 6, padding: '8px 12px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>
                  {icon} {label}
                </div>
                <div style={{
                  color: '#c8d8ec', fontSize: '0.78rem', fontWeight: 600,
                  fontFamily: mono ? 'monospace' : 'inherit',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Prediction scope badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '7px 12px',
            background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)',
            borderRadius: 6,
          }}>
            <Activity size={13} color="#3b82f6" />
            <span style={{ color: '#60a5fa', fontSize: '0.75rem', fontWeight: 700 }}>
              NETWORK-LEVEL PREDICTION
            </span>
            <span style={{ color: '#2a4060', fontSize: '0.7rem' }}>
              — model operates on aggregated network states
            </span>
          </div>

          {/* Current prediction */}
          {cs && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10,
            }}>
              {[
                { label: 'Stage',       value: cs.stage,                         color: '#c8d8ec' },
                { label: 'Attack Prob', value: `${(cs.attack_probability * 100).toFixed(1)}%`, color: cs.attack_probability >= 0.5 ? '#ef4444' : '#22c55e' },
                { label: 'Confidence',  value: `${(cs.stage_confidence * 100).toFixed(1)}%`,  color: '#7d95b5' },
                { label: 'Risk',        value: cs.risk,                           color: riskColor(cs.risk) },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
                  <div style={{ color, fontSize: '0.88rem', fontWeight: 700 }}>{value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Entity / device summary */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10,
          }}>
            <div style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>
                <Monitor size={11} /> Entity IDs
              </div>
              <div style={{ color: hasEntityIds ? '#22c55e' : '#f59e0b', fontSize: '0.88rem', fontWeight: 700 }}>
                {hasEntityIds ? 'Present' : 'Not found'}
              </div>
              <div style={{ color: '#1e3a5f', fontSize: '0.65rem', marginTop: 2 }}>
                {hasEntityIds ? `${totalEnts} unique src IPs` : 'Network-level view only'}
              </div>
            </div>

            {hasEntityIds && (
              <>
                <div style={{ background: '#070d1a', border: `1px solid ${highRisk > 0 ? '#ef444433' : '#1a2c4a'}`, borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>
                    <AlertTriangle size={11} /> High-Risk Devices
                  </div>
                  <div style={{ color: highRisk > 0 ? '#ef4444' : '#22c55e', fontSize: '0.88rem', fontWeight: 700 }}>
                    {highRisk} / {totalEnts}
                  </div>
                </div>

                <div style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>
                    <Monitor size={11} /> Active Entity
                  </div>
                  <div style={{ color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.78rem', fontWeight: 600 }}>
                    {selectedEntity?.entity_id ?? 'None selected'}
                  </div>
                </div>
              </>
            )}

            {!hasEntityIds && (
              <div style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
                <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>Network Risk</div>
                <div style={{ color: riskColor(netRisk), fontSize: '0.88rem', fontWeight: 700 }}>{netRisk ?? '—'}</div>
              </div>
            )}
          </div>

          {/* Clear button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={resetAnalysis}
              style={{
                padding: '5px 14px',
                background: 'none', border: '1px solid #1a2c4a',
                borderRadius: 5, color: '#3d5275',
                fontSize: '0.72rem', cursor: 'pointer',
              }}
            >
              Clear analysis
            </button>
          </div>
        </div>
      )}
    </Panel>
  )
}

// ── Alert configuration panel ──────────────────────────────────────────────

function AlertConfigPanel() {
  const [status,   setStatus]   = useState<AlertStatusResponse | null>(null)
  const [loading,  setLoading]  = useState(true)
  const [testing,  setTesting]  = useState(false)
  const [testResult, setTestResult] = useState<AlertTestResponse | null>(null)
  const [testError,  setTestError]  = useState<string | null>(null)

  function fetchStatus() {
    setLoading(true)
    getAlertStatus()
      .then(s => setStatus(s))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchStatus() }, [])

  async function handleTestAlert() {
    setTesting(true); setTestResult(null); setTestError(null)
    try {
      const r = await testAlert()
      setTestResult(r)
    } catch (e) {
      setTestError(e instanceof Error ? e.message : 'Test failed')
    } finally {
      setTesting(false)
    }
  }

  const configItems = status ? [
    { label: 'Alerts Enabled',     ok: status.enabled },
    { label: 'SMTP Configured',    ok: status.smtp_configured },
    { label: 'Recipient Set',      ok: status.recipient_configured },
    { label: 'Fully Configured',   ok: status.configured },
  ] : []

  return (
    <Panel
      title="Email Alert Configuration"
      subtitle="GET /alerts/status — configure via .env file"
      action={
        <button
          onClick={fetchStatus}
          style={{
            background: 'none', border: 'none',
            color: '#3d5275', fontSize: '0.72rem', cursor: 'pointer',
          }}
        >
          ↻ Refresh
        </button>
      }
    >
      {loading ? (
        <LoadingSkeleton lines={3} height={80} />
      ) : status ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Status grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
            {configItems.map(({ label, ok }) => (
              <div key={label} style={{
                background: '#070d1a',
                border: `1px solid ${ok ? '#22c55e33' : '#ef444433'}`,
                borderTop: `2px solid ${ok ? '#22c55e' : '#ef4444'}`,
                borderRadius: 7, padding: '10px 12px',
              }}>
                <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>
                  {label}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {ok
                    ? <CheckCircle size={14} color="#22c55e" />
                    : <XCircle    size={14} color="#ef4444" />}
                  <span style={{ color: ok ? '#4ade80' : '#f87171', fontSize: '0.82rem', fontWeight: 700 }}>
                    {ok ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Configuration instructions */}
          {!status.configured && (
            <div style={{
              padding: '10px 14px',
              background: 'rgba(245,158,11,0.05)',
              border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: 6, color: '#927a5a', fontSize: '0.75rem', lineHeight: 1.6,
            }}>
              <div style={{ color: '#f59e0b', fontWeight: 700, marginBottom: 4 }}>
                ⚙ Configure email alerts
              </div>
              Set these variables in{' '}
              <code style={{ color: '#c8d8ec' }}>.env</code> at the project root:
              <pre style={{
                background: '#070d1a', borderRadius: 5,
                padding: '8px 12px', marginTop: 8, marginBottom: 0,
                fontFamily: 'monospace', fontSize: '0.75rem', color: '#4ade80',
                overflow: 'auto',
              }}>
{`SMTP_EMAIL=sender@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password
ALERT_RECEIVER_EMAIL=soc@example.com`}
              </pre>
            </div>
          )}

          {/* Test button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <button
              onClick={handleTestAlert}
              disabled={testing || !status.configured}
              title={!status.configured ? 'Configure SMTP first' : 'Send a test alert email'}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '7px 18px',
                background: status.configured ? '#0d1d3c' : '#111e35',
                border: `1px solid ${status.configured ? '#3b82f6' : '#1a2c4a'}`,
                borderRadius: 6,
                color: status.configured ? '#93c5fd' : '#3d5275',
                fontSize: '0.8rem', fontWeight: 600,
                cursor: status.configured && !testing ? 'pointer' : 'not-allowed',
                opacity: testing ? 0.7 : 1,
              }}
            >
              {testing
                ? <><Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> Sending…</>
                : <><Send size={13} /> <Mail size={13} /> Send Test Alert</>
              }
            </button>

            {testResult && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '5px 12px',
                background: testResult.success ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${testResult.success ? '#22c55e44' : '#ef444444'}`,
                borderRadius: 5, fontSize: '0.78rem',
                color: testResult.success ? '#4ade80' : '#f87171',
              }}>
                {testResult.success
                  ? <CheckCircle size={13} />
                  : <XCircle    size={13} />}
                {testResult.message}
              </div>
            )}

            {testError && (
              <div style={{
                color: '#ef4444', fontSize: '0.75rem',
                padding: '5px 10px',
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.2)',
                borderRadius: 5,
              }}>
                {testError}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ color: '#2a4060', fontSize: '0.82rem' }}>
          Alert status unavailable. Is the backend running?
        </div>
      )}
      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </Panel>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SystemStatus() {
  const [health,    setHealth]    = useState<HealthResponse | null>(null)
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState<string | null>(null)

  function fetchAll() {
    setLoading(true); setError(null)
    Promise.all([getHealth(), getModelInfo()])
      .then(([h, m]) => { setHealth(h); setModelInfo(m) })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to load system info'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchAll() }, [])

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
            System Status
          </h1>
          <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
            Backend API health, World Model architecture, and alert configuration
          </p>
        </div>
        <button onClick={fetchAll} style={{
          padding: '6px 16px', background: '#0d1526',
          border: '1px solid #1a2c4a', borderRadius: 6,
          color: '#5d7a9a', fontSize: '0.78rem', cursor: 'pointer',
        }}>
          ↻ Refresh
        </button>
      </div>

      {error && !loading && <ErrorState error={error} onRetry={fetchAll} />}

      {/* API status banner */}
      <Panel title="API Status">
        {loading ? <LoadingSkeleton lines={3} height={80} /> : health ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%',
              background: health.status.toLowerCase().includes('health') ? '#22c55e1a' : '#ef44441a',
              border: `2px solid ${health.status.toLowerCase().includes('health') ? '#22c55e' : '#ef4444'}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
            }}>
              <Server size={20} color={health.status.toLowerCase().includes('health') ? '#22c55e' : '#ef4444'} />
            </div>
            <div>
              <div style={{
                color: health.status.toLowerCase().includes('health') ? '#4ade80' : '#ef4444',
                fontSize: '1rem', fontWeight: 800, textTransform: 'uppercase',
              }}>
                {health.status}
              </div>
              <div style={{ color: '#3d5275', fontSize: '0.75rem', marginTop: 2 }}>
                {health.model}
              </div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
              <div style={{
                padding: '2px 10px',
                background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)',
                borderRadius: 20, color: '#4ade80', fontSize: '0.72rem', fontWeight: 600,
              }}>
                ● CONNECTED
              </div>
              <div style={{ color: '#1e3a5f', fontSize: '0.68rem' }}>
                http://127.0.0.1:8000
              </div>
            </div>
          </div>
        ) : null}
      </Panel>

      {/* Current analysis status */}
      <AnalysisStatusPanel />

      {/* Model architecture cards */}
      <div>
        <div style={{
          color: '#3d5275', fontSize: '0.68rem', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10,
        }}>
          Model Architecture
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
          {loading ? (
            Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)
          ) : modelInfo ? (
            <>
              <MetricCard label="Model Type"         value={modelInfo.model_type}                      accentColor="#3b82f6" icon={<Layers size={16} />} />
              <MetricCard label="Device"             value={modelInfo.device.toUpperCase()}            accentColor="#06b6d4" icon={<Cpu size={16} />} />
              <MetricCard label="Input Shape"        value={`${modelInfo.sequence_length} × ${modelInfo.num_features}`} sub="seq_len × features" accentColor="#8b5cf6" />
              <MetricCard label="Parameters"        value={modelInfo.parameters.toLocaleString()}     accentColor="#f59e0b" icon={<Hash size={16} />} sub="trainable params" />
              <MetricCard label="Sequence Length"   value={String(modelInfo.sequence_length)}         accentColor="#22c55e" icon={<GitBranch size={16} />} sub="temporal steps" />
              <MetricCard label="Feature Dimensions" value={String(modelInfo.num_features)}            accentColor="#06b6d4" sub="network features" />
              <MetricCard label="Attack Stages"     value={String(modelInfo.num_stages)}              accentColor="#f97316" sub="classification classes" />
              <MetricCard label="Forecast Horizon"  value={`${modelInfo.autoregressive_horizon} Steps`} accentColor="#7c3aed" icon={<Activity size={16} />} sub="autoregressive" />
            </>
          ) : null}
        </div>
      </div>

      {/* Alert configuration */}
      <AlertConfigPanel />

      {/* Endpoint reference */}
      <Panel title="Available API Endpoints" subtitle="All endpoints served by the FastAPI backend">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
          {[
            { method: 'GET',  path: '/health',                    tag: 'System',   desc: 'API health check' },
            { method: 'GET',  path: '/model/info',                tag: 'System',   desc: 'Model architecture details' },
            { method: 'GET',  path: '/samples',                   tag: 'Dataset',  desc: 'Test dataset metadata' },
            { method: 'GET',  path: '/predict/{id}',              tag: 'Inference',desc: 'Single-step prediction' },
            { method: 'GET',  path: '/forecast/{id}',             tag: 'Inference',desc: '5-step autoregressive forecast' },
            { method: 'GET',  path: '/forecast/{id}/states',      tag: 'Inference',desc: '44-feature state vectors' },
            { method: 'GET',  path: '/explain/{id}',              tag: 'XAI',      desc: 'Feature sensitivity' },
            { method: 'GET',  path: '/model/comparison',          tag: 'Model',    desc: 'Performance comparison' },
            { method: 'POST', path: '/upload',                    tag: 'Upload',   desc: 'Upload CSV telemetry' },
            { method: 'POST', path: '/analyze/{upload_id}',       tag: 'Upload',   desc: 'Run analysis pipeline' },
            { method: 'GET',  path: '/analysis/{id}',             tag: 'Upload',   desc: 'Retrieve analysis result' },
            { method: 'GET',  path: '/analysis/{id}/states',      tag: 'Upload',   desc: 'Analysis time-window states' },
            { method: 'GET',  path: '/analysis/{id}/entities',    tag: 'Upload',   desc: 'Entity/device identifiers + risk' },
            { method: 'GET',  path: '/analysis/{id}/forecast',    tag: 'Upload',   desc: 'Analysis forecast steps' },
            { method: 'GET',  path: '/analysis/{id}/explain',     tag: 'Upload',   desc: 'Analysis feature sensitivity' },
            { method: 'GET',  path: '/analysis/{id}/metrics',     tag: 'Upload',   desc: 'Analysis evaluation metrics' },
            { method: 'GET',  path: '/alerts/status',             tag: 'Alerts',   desc: 'Email alert config status' },
            { method: 'POST', path: '/alerts/test',               tag: 'Alerts',   desc: 'Send test alert email' },
          ].map(({ method, path, tag }) => {
            const mc = method === 'GET' ? '#06b6d4' : '#f59e0b'
            return (
              <div key={path} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '6px 10px',
                background: '#070d1a', border: '1px solid #0f1d33', borderRadius: 5,
              }}>
                <span style={{
                  background: `${mc}18`, border: `1px solid ${mc}44`,
                  borderRadius: 4, padding: '1px 7px',
                  color: mc, fontSize: '0.65rem', fontWeight: 700,
                  minWidth: 36, textAlign: 'center', flexShrink: 0,
                }}>
                  {method}
                </span>
                <span style={{ color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.75rem', flex: 1 }}>
                  {path}
                </span>
                <span style={{
                  color: '#2a4060', fontSize: '0.65rem',
                  background: '#111e35', borderRadius: 3, padding: '1px 6px', flexShrink: 0,
                }}>
                  {tag}
                </span>
              </div>
            )
          })}
        </div>
        <div style={{ marginTop: 10, color: '#1e3a5f', fontSize: '0.68rem' }}>
          Swagger UI: <span style={{ color: '#3b82f6', fontFamily: 'monospace' }}>http://127.0.0.1:8000/docs</span>
        </div>
      </Panel>

      {/* Raw health response */}
      {health && (
        <Panel title="Raw /health Response">
          <pre style={{
            background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6,
            padding: '12px 16px', color: '#7d95b5', fontSize: '0.78rem',
            lineHeight: 1.7, overflow: 'auto', margin: 0,
          }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        </Panel>
      )}

      {/* Raw model/info response */}
      {modelInfo && (
        <Panel title="Raw /model/info Response">
          <pre style={{
            background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6,
            padding: '12px 16px', color: '#7d95b5', fontSize: '0.78rem',
            lineHeight: 1.7, overflow: 'auto', margin: 0,
          }}>
            {JSON.stringify(modelInfo, null, 2)}
          </pre>
        </Panel>
      )}

      {/* Backend run command */}
      <Panel title="Backend Start Command" subtitle="Run from project root">
        <div style={{
          background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6,
          padding: '10px 16px', fontFamily: 'monospace', color: '#4ade80', fontSize: '0.82rem',
        }}>
          python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
        </div>
        <div style={{ marginTop: 8, color: '#1e3a5f', fontSize: '0.72rem' }}>
          Swagger UI: http://127.0.0.1:8000/docs &nbsp;·&nbsp; Frontend: http://localhost:5173
        </div>
      </Panel>
    </div>
  )
}
