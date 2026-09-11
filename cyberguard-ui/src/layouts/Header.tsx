import { RefreshCw, Clock, UploadCloud, CheckCircle, Monitor } from 'lucide-react'
import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useSampleContext }   from '../context/SampleContext'
import { useAnalysisContext } from '../context/AnalysisContext'

export default function Header() {
  const { refresh }                                       = useSampleContext()
  const { hasAnalysis, analysisLabel, entitiesData,
          selectedEntity, analysisLoading }               = useAnalysisContext()
  const [now, setNow]         = useState(new Date())
  const [spinning, setSpinning] = useState(false)

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  function handleRefresh() {
    setSpinning(true)
    refresh()
    setTimeout(() => setSpinning(false), 800)
  }

  const timeStr = now.toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  // ── Derive the primary status indicator from AnalysisContext ──────────────
  // When an analysis is loaded we show the active entity / network scope.
  // "Sample #N" is no longer the primary user-facing concept.

  const totalEntities  = entitiesData?.total_entities  ?? 0
  const hasEntityIds   = entitiesData?.has_entity_ids  ?? false
  const highRisk       = entitiesData?.high_risk_count ?? 0
  const netRisk        = entitiesData?.network_prediction?.risk ?? null

  return (
    <header style={{
      height: 48,
      background: '#060d1a',
      borderBottom: '1px solid #0f1d33',
      display: 'flex', alignItems: 'center',
      padding: '0 20px',
      gap: 12,
      flexShrink: 0,
    }}>
      {/* Left: product title */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ color: '#c8d8ec', fontSize: '0.82rem', fontWeight: 700 }}>
          AI World Model for Predictive Cyber Defence
        </span>
        <span style={{ color: '#1e3a5f', fontSize: '0.8rem' }}>|</span>
        <span style={{ color: '#2a4060', fontSize: '0.72rem' }}>SIH Research Demo</span>
      </div>

      <div style={{ flex: 1 }} />

      {/* ── Primary status indicator ── */}
      {analysisLoading ? (
        /* Analysis running */
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 12px',
          background: 'rgba(59,130,246,0.08)',
          border: '1px solid rgba(59,130,246,0.22)',
          borderRadius: 20,
        }}>
          <span className="pulse-dot" style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#3b82f6', display: 'inline-block',
          }} />
          <span style={{ color: '#3b82f6', fontSize: '0.7rem', fontWeight: 700 }}>
            ANALYSING…
          </span>
        </div>

      ) : hasAnalysis ? (
        /* Analysis loaded — show entity / network status */
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '3px 12px',
          background: highRisk > 0
            ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${highRisk > 0
            ? 'rgba(239,68,68,0.22)' : 'rgba(34,197,94,0.22)'}`,
          borderRadius: 20,
        }}>
          <span className="pulse-dot" style={{
            width: 6, height: 6, borderRadius: '50%',
            background: highRisk > 0 ? '#ef4444' : '#22c55e',
            display: 'inline-block',
          }} />
          {hasEntityIds ? (
            <>
              <Monitor size={11} color={highRisk > 0 ? '#ef4444' : '#22c55e'} />
              <span style={{
                color: highRisk > 0 ? '#ef4444' : '#4ade80',
                fontSize: '0.7rem', fontWeight: 700,
              }}>
                {totalEntities} DEVICE{totalEntities !== 1 ? 'S' : ''}
              </span>
              {highRisk > 0 && (
                <span style={{ color: '#ef4444', fontSize: '0.68rem' }}>
                  · {highRisk} HIGH RISK
                </span>
              )}
            </>
          ) : (
            <>
              <span style={{ color: '#4ade80', fontSize: '0.7rem', fontWeight: 700 }}>
                NETWORK-LEVEL
              </span>
              {netRisk && (
                <span style={{
                  color: netRisk === 'HIGH' || netRisk === 'CRITICAL'
                    ? '#ef4444' : netRisk === 'MEDIUM' ? '#f59e0b' : '#22c55e',
                  fontSize: '0.68rem',
                }}>
                  · {netRisk}
                </span>
              )}
            </>
          )}
        </div>

      ) : (
        /* No analysis — nudge user to upload */
        <Link
          to="/upload"
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '3px 12px',
            background: 'rgba(59,130,246,0.08)',
            border: '1px solid rgba(59,130,246,0.22)',
            borderRadius: 20, textDecoration: 'none',
          }}
        >
          <UploadCloud size={11} color="#3b82f6" />
          <span style={{ color: '#3b82f6', fontSize: '0.7rem', fontWeight: 700 }}>
            UPLOAD TELEMETRY
          </span>
        </Link>
      )}

      {/* Active entity pill (when a device is selected) */}
      {selectedEntity && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '2px 10px',
          background: '#0a1425', border: '1px solid #1a2c4a',
          borderRadius: 5,
        }}>
          <Monitor size={11} color="#7d95b5" />
          <span style={{
            color: '#93c5fd', fontFamily: 'monospace',
            fontSize: '0.72rem', fontWeight: 700,
          }}>
            {selectedEntity.entity_id}
          </span>
        </div>
      )}

      {/* Analysis filename pill (when loaded, no device selected) */}
      {hasAnalysis && !selectedEntity && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '2px 10px',
          background: '#0a1425', border: '1px solid #1a2c4a',
          borderRadius: 5,
          maxWidth: 200, overflow: 'hidden',
        }}>
          <CheckCircle size={11} color="#22c55e" />
          <span style={{
            color: '#7d95b5', fontSize: '0.7rem',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {analysisLabel}
          </span>
        </div>
      )}

      {/* Clock */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        color: '#2a4060', fontSize: '0.72rem',
      }}>
        <Clock size={12} />
        <span style={{ fontFamily: 'monospace', color: '#3d5275' }}>{timeStr}</span>
      </div>

      {/* Refresh (refreshes the legacy sample-based view) */}
      <button
        onClick={handleRefresh}
        title="Refresh demo data"
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '4px 10px',
          background: '#0a1425', border: '1px solid #1a2c4a',
          borderRadius: 5, color: '#4d6a8a',
          cursor: 'pointer', fontSize: '0.72rem',
        }}
      >
        <RefreshCw
          size={12}
          style={{
            transition: 'transform 0.4s',
            transform: spinning ? 'rotate(360deg)' : 'none',
          }}
        />
        Refresh
      </button>
    </header>
  )
}
