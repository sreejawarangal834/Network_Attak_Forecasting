import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Network, TrendingUp, Layers,
  Lightbulb, BarChart2, Activity, Shield,
  ChevronLeft, ChevronRight, UploadCloud,
  Monitor, AlertTriangle,
} from 'lucide-react'
import { useState } from 'react'
import ApiStatus  from '../components/ApiStatus'
import SampleSelector from '../components/SampleSelector'
import { useAnalysisContext } from '../context/AnalysisContext'

// ─────────────────────────────────────────────────────────────────────────────
// Nav structure
// ─────────────────────────────────────────────────────────────────────────────

const NAV_SECTIONS = [
  {
    label: 'MAIN',
    items: [
      { to: '/',           label: 'Dashboard',        icon: <LayoutDashboard size={16} /> },
      { to: '/network',    label: 'Network State',     icon: <Network size={16} /> },
      { to: '/forecast',   label: 'Attack Forecast',   icon: <TrendingUp size={16} /> },
    ],
  },
  {
    label: 'ANALYSIS',
    items: [
      { to: '/stages',      label: 'Attack Stages',    icon: <Layers size={16} /> },
      { to: '/explain',     label: 'Explainability',   icon: <Lightbulb size={16} /> },
      { to: '/performance', label: 'Model Performance',icon: <BarChart2 size={16} /> },
    ],
  },
  {
    label: 'DATA',
    items: [
      { to: '/upload', label: 'Upload Telemetry', icon: <UploadCloud size={16} /> },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { to: '/system', label: 'System Status', icon: <Activity size={16} /> },
    ],
  },
]

const NAV_LINK_BASE: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10,
  padding: '7px 14px', borderRadius: 6,
  textDecoration: 'none', fontSize: '0.82rem', fontWeight: 500,
  color: '#4d6a8a', transition: 'all 0.15s',
  cursor: 'pointer', userSelect: 'none',
}

// ─────────────────────────────────────────────────────────────────────────────
// Analysis status panel (shown in sidebar when an analysis is loaded)
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisStatus() {
  const {
    hasAnalysis, analysisLabel, entitiesData,
    selectedEntityId, selectedEntity, selectEntity,
    resetAnalysis,
  } = useAnalysisContext()

  if (!hasAnalysis) {
    // Prompt to upload
    return (
      <div style={{ padding: '10px 14px' }}>
        <div style={{
          color: '#1e3a5f', fontSize: '0.6rem', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8,
        }}>
          ACTIVE ANALYSIS
        </div>
        <NavLink
          to="/upload"
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '7px 10px',
            background: 'rgba(59,130,246,0.08)',
            border: '1px dashed rgba(59,130,246,0.3)',
            borderRadius: 6, textDecoration: 'none',
            color: '#3b82f6', fontSize: '0.75rem', fontWeight: 600,
          }}
        >
          <UploadCloud size={13} />
          Upload Telemetry
        </NavLink>
        <div style={{ color: '#1e3a5f', fontSize: '0.62rem', marginTop: 6 }}>
          Upload a CSV to enable device-centric analysis.
        </div>
      </div>
    )
  }

  const hasEntityIds  = entitiesData?.has_entity_ids  ?? false
  const totalEntities = entitiesData?.total_entities  ?? 0
  const highRisk      = entitiesData?.high_risk_count ?? 0
  const entities      = entitiesData?.entities        ?? []
  const netRisk       = entitiesData?.network_prediction?.risk ?? '—'

  // Show top 5 entities in the sidebar for quick selection
  const topEntities   = entities.slice(0, 5)

  const riskColor = (r: string) =>
    r === 'CRITICAL' ? '#7c3aed'
    : r === 'HIGH'   ? '#ef4444'
    : r === 'MEDIUM' ? '#f59e0b'
    : '#22c55e'

  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Header row */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{
          color: '#1e3a5f', fontSize: '0.6rem', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.1em',
        }}>
          ACTIVE ANALYSIS
        </div>
        <button
          onClick={resetAnalysis}
          title="Clear analysis"
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: '#1e3a5f', fontSize: '0.62rem', padding: '0 2px',
          }}
        >
          ✕
        </button>
      </div>

      {/* Filename */}
      <div style={{
        color: '#5d7a9a', fontSize: '0.7rem', fontFamily: 'monospace',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
      }}>
        {analysisLabel}
      </div>

      {hasEntityIds ? (
        <>
          {/* Device count summary */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5,
          }}>
            <div style={{
              background: '#070d1a', border: '1px solid #1a2c4a',
              borderRadius: 5, padding: '5px 8px',
            }}>
              <div style={{ color: '#3d5275', fontSize: '0.58rem' }}>DEVICES</div>
              <div style={{ color: '#c8d8ec', fontSize: '0.9rem', fontWeight: 700 }}>
                {totalEntities}
              </div>
            </div>
            <div style={{
              background: '#070d1a',
              border: `1px solid ${highRisk > 0 ? '#ef444433' : '#1a2c4a'}`,
              borderRadius: 5, padding: '5px 8px',
            }}>
              <div style={{ color: '#3d5275', fontSize: '0.58rem' }}>HIGH RISK</div>
              <div style={{
                color: highRisk > 0 ? '#ef4444' : '#22c55e',
                fontSize: '0.9rem', fontWeight: 700,
              }}>
                {highRisk}
              </div>
            </div>
          </div>

          {/* Top entities quick-select */}
          {topEntities.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{
                color: '#1e3a5f', fontSize: '0.58rem', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.08em',
                marginBottom: 2,
              }}>
                DEVICES
              </div>
              {topEntities.map(ent => {
                const isSelected = ent.entity_id === selectedEntityId
                const c = riskColor(ent.risk)
                return (
                  <button
                    key={ent.entity_id}
                    onClick={() => selectEntity(
                      isSelected ? null : ent.entity_id
                    )}
                    title={ent.entity_id}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '5px 8px',
                      background: isSelected ? '#0f1d33' : '#070d1a',
                      border: `1px solid ${isSelected ? '#3b82f6' : '#1a2c4a'}`,
                      borderLeft: `2px solid ${isSelected ? '#3b82f6' : c}`,
                      borderRadius: 5, cursor: 'pointer',
                      textAlign: 'left', width: '100%',
                    }}
                  >
                    <Monitor size={11} color={c} style={{ flexShrink: 0 }} />
                    <span style={{
                      color: '#c8d8ec', fontFamily: 'monospace', fontSize: '0.7rem',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      flex: 1, fontWeight: isSelected ? 700 : 400,
                    }}>
                      {ent.entity_id}
                    </span>
                    <span style={{ color: c, fontSize: '0.58rem', fontWeight: 700, flexShrink: 0 }}>
                      {ent.risk}
                    </span>
                  </button>
                )
              })}
              {entities.length > 5 && (
                <NavLink
                  to="/"
                  style={{
                    color: '#2a4060', fontSize: '0.65rem',
                    textDecoration: 'none', padding: '2px 8px',
                  }}
                >
                  +{entities.length - 5} more → Dashboard
                </NavLink>
              )}
            </div>
          )}

          {selectedEntity && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 8px',
              background: 'rgba(59,130,246,0.06)',
              border: '1px solid rgba(59,130,246,0.2)',
              borderRadius: 5,
            }}>
              <Monitor size={11} color="#3b82f6" style={{ flexShrink: 0 }} />
              <span style={{
                color: '#93c5fd', fontFamily: 'monospace', fontSize: '0.7rem',
                fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {selectedEntity.entity_id}
              </span>
            </div>
          )}
        </>
      ) : (
        /* Network-level only */
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 8px',
          background: 'rgba(59,130,246,0.06)',
          border: '1px solid rgba(59,130,246,0.18)',
          borderRadius: 5,
        }}>
          <AlertTriangle size={11} color="#3b82f6" style={{ flexShrink: 0 }} />
          <div>
            <div style={{ color: '#93c5fd', fontSize: '0.65rem', fontWeight: 700 }}>
              NETWORK-LEVEL
            </div>
            <div style={{ color: riskColor(netRisk), fontSize: '0.65rem' }}>
              {netRisk}
            </div>
          </div>
        </div>
      )}

      {/* Upload new file link */}
      <NavLink
        to="/upload"
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          color: '#2a4060', fontSize: '0.65rem', textDecoration: 'none',
          marginTop: 2,
        }}
      >
        <UploadCloud size={11} /> Upload new file
      </NavLink>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Developer section — SampleSelector (debug/demo only)
// ─────────────────────────────────────────────────────────────────────────────

function DeveloperSection() {
  const [open, setOpen] = useState(false)
  return (
    <div style={{ borderTop: '1px solid #0f1d33' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          width: '100%', padding: '8px 14px',
          background: 'none', border: 'none', cursor: 'pointer',
          color: '#1e3a5f', fontSize: '0.6rem', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.1em',
          justifyContent: 'space-between',
        }}
      >
        <span>DEVELOPER / DEMO</span>
        {open ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && (
        <div style={{ padding: '4px 14px 12px' }}>
          <div style={{
            color: '#1e3a5f', fontSize: '0.62rem', marginBottom: 8, lineHeight: 1.5,
          }}>
            Pre-built test set sample selector. Used by the demo/developer
            fallback view only — not the primary product interface.
          </div>
          <SampleSelector />
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root Sidebar component
// ─────────────────────────────────────────────────────────────────────────────

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const w = collapsed ? 54 : 224

  return (
    <aside style={{
      width: w, minWidth: w, height: '100vh',
      background: '#060d1a',
      borderRight: '1px solid #0f1d33',
      display: 'flex', flexDirection: 'column',
      transition: 'width 0.2s ease',
      overflowX: 'hidden', flexShrink: 0,
      position: 'relative',
    }}>
      {/* Brand */}
      <div style={{
        padding: collapsed ? '16px 0' : '16px 14px',
        borderBottom: '1px solid #0f1d33',
        display: 'flex', alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'flex-start',
        gap: 8,
      }}>
        <Shield size={20} color="#3b82f6" style={{ flexShrink: 0 }} />
        {!collapsed && (
          <div>
            <div style={{ color: '#3b82f6', fontSize: '0.9rem', fontWeight: 800, letterSpacing: '0.06em' }}>
              AI CYBER DEFENCE
            </div>
            <div style={{ color: '#2a4060', fontSize: '0.62rem', marginTop: 1 }}>
              World Model System
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        {NAV_SECTIONS.map(section => (
          <div key={section.label} style={{ marginBottom: 8 }}>
            {!collapsed && (
              <div style={{
                color: '#1e3a5f', fontSize: '0.6rem', fontWeight: 700,
                textTransform: 'uppercase', letterSpacing: '0.1em',
                padding: '8px 14px 4px',
              }}>
                {section.label}
              </div>
            )}
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                title={collapsed ? item.label : undefined}
                style={({ isActive }) => ({
                  ...NAV_LINK_BASE,
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  color:      isActive ? '#e2e8f0' : '#4d6a8a',
                  background: isActive ? '#0f1d33' : 'transparent',
                  borderLeft: isActive ? '3px solid #3b82f6' : '3px solid transparent',
                  paddingLeft: collapsed ? 0 : isActive ? 11 : 14,
                })}
              >
                <span style={{ flexShrink: 0 }}>{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Analysis status panel (primary — replaces SampleSelector as main widget) */}
      {!collapsed && (
        <div style={{ borderTop: '1px solid #0f1d33' }}>
          <AnalysisStatus />
        </div>
      )}

      {/* Developer / demo section (collapsed by default) */}
      {!collapsed && <DeveloperSection />}

      {/* API status + collapse toggle */}
      <div style={{
        padding: collapsed ? '12px 0' : '12px 14px',
        borderTop: '1px solid #0f1d33',
        display: 'flex', flexDirection: 'column',
        alignItems: collapsed ? 'center' : 'stretch',
        gap: 8,
      }}>
        {!collapsed && <ApiStatus />}

        <button
          onClick={() => setCollapsed(c => !c)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            width: '100%', padding: '5px 0',
            background: 'none', border: 'none',
            color: '#1e3a5f', cursor: 'pointer',
            fontSize: '0.7rem',
          }}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          {!collapsed && <span style={{ marginLeft: 4 }}>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
