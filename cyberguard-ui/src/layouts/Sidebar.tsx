import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Network, TrendingUp, Layers,
  Lightbulb, BarChart2, Activity, Shield, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useState } from 'react'
import SampleSelector from '../components/SampleSelector'
import ApiStatus from '../components/ApiStatus'

const NAV_SECTIONS = [
  {
    label: 'MAIN',
    items: [
      { to: '/',           label: 'Dashboard',       icon: <LayoutDashboard size={16} /> },
      { to: '/network',    label: 'Network State',    icon: <Network size={16} /> },
      { to: '/forecast',   label: 'Attack Forecast',  icon: <TrendingUp size={16} /> },
    ],
  },
  {
    label: 'ANALYSIS',
    items: [
      { to: '/stages',     label: 'Attack Stages',    icon: <Layers size={16} /> },
      { to: '/explain',    label: 'Explainability',   icon: <Lightbulb size={16} /> },
      { to: '/performance',label: 'Model Performance',icon: <BarChart2 size={16} /> },
    ],
  },
  {
    label: 'SYSTEM',
    items: [
      { to: '/system',     label: 'System Status',    icon: <Activity size={16} /> },
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

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const w = collapsed ? 54 : 220

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
                  color: isActive ? '#e2e8f0' : '#4d6a8a',
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

      {/* Sample selector */}
      {!collapsed && (
        <div style={{
          padding: '12px 14px',
          borderTop: '1px solid #0f1d33',
          borderBottom: '1px solid #0f1d33',
        }}>
          <SampleSelector />
        </div>
      )}

      {/* API status + collapse toggle */}
      <div style={{
        padding: collapsed ? '12px 0' : '12px 14px',
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
