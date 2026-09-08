/**
 * SystemStatus.tsx — API + model health page.
 *
 * Consumes: GET /health, GET /model/info
 */

import { useEffect, useState } from 'react'
import { Activity, Cpu, Layers, Hash, GitBranch, Server } from 'lucide-react'

import { getHealth, getModelInfo } from '../services/api'
import type { HealthResponse, ModelInfoResponse } from '../types/api'

import Panel from '../components/Panel'
import MetricCard from '../components/MetricCard'
import LoadingSkeleton, { CardSkeleton } from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

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

      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
            System Status
          </h1>
          <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
            Backend API health and World Model architecture information
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
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
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
            <div style={{
              marginLeft: 'auto', display: 'flex', flexDirection: 'column',
              alignItems: 'flex-end', gap: 4,
            }}>
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

      {/* Model info cards */}
      <div>
        <div style={{ color: '#3d5275', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
          Model Architecture
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
          {loading ? (
            Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)
          ) : modelInfo ? (
            <>
              <MetricCard label="Model Type"          value={modelInfo.model_type}       accentColor="#3b82f6" icon={<Layers size={16} />} />
              <MetricCard label="Device"              value={modelInfo.device.toUpperCase()} accentColor="#06b6d4" icon={<Cpu size={16} />} />
              <MetricCard label="Input Shape"         value={`${modelInfo.sequence_length} × ${modelInfo.num_features}`}
                sub="seq_len × features" accentColor="#8b5cf6" />
              <MetricCard label="Parameters"         value={modelInfo.parameters.toLocaleString()}
                sub="trainable params" accentColor="#f59e0b" icon={<Hash size={16} />} />
              <MetricCard label="Sequence Length"    value={String(modelInfo.sequence_length)}
                sub="temporal steps" accentColor="#22c55e" icon={<GitBranch size={16} />} />
              <MetricCard label="Feature Dimensions" value={String(modelInfo.num_features)}
                sub="network features" accentColor="#06b6d4" />
              <MetricCard label="Attack Stages"      value={String(modelInfo.num_stages)}
                sub="classification classes" accentColor="#f97316" />
              <MetricCard label="Forecast Horizon"   value={`${modelInfo.autoregressive_horizon} Steps`}
                sub="autoregressive" accentColor="#7c3aed" icon={<Activity size={16} />} />
            </>
          ) : null}
        </div>
      </div>

      {/* Health raw response */}
      {health && (
        <Panel title="Raw /health Response">
          <pre style={{
            background: '#070d1a', border: '1px solid #1a2c4a',
            borderRadius: 6, padding: '12px 16px',
            color: '#7d95b5', fontSize: '0.78rem', lineHeight: 1.7,
            overflow: 'auto', margin: 0,
          }}>
            {JSON.stringify(health, null, 2)}
          </pre>
        </Panel>
      )}

      {/* Model info raw response */}
      {modelInfo && (
        <Panel title="Raw /model/info Response">
          <pre style={{
            background: '#070d1a', border: '1px solid #1a2c4a',
            borderRadius: 6, padding: '12px 16px',
            color: '#7d95b5', fontSize: '0.78rem', lineHeight: 1.7,
            overflow: 'auto', margin: 0,
          }}>
            {JSON.stringify(modelInfo, null, 2)}
          </pre>
        </Panel>
      )}

      {/* Backend run command */}
      <Panel title="Backend Start Command" subtitle="Run this to start the FastAPI backend">
        <div style={{
          background: '#070d1a', border: '1px solid #1a2c4a',
          borderRadius: 6, padding: '10px 16px',
          fontFamily: 'monospace', color: '#4ade80', fontSize: '0.82rem',
        }}>
          python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
        </div>
        <div style={{ marginTop: 8, color: '#1e3a5f', fontSize: '0.72rem' }}>
          Swagger UI: http://127.0.0.1:8000/docs &nbsp;·&nbsp;
          Frontend: http://localhost:5173
        </div>
      </Panel>
    </div>
  )
}
