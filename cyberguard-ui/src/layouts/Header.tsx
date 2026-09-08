import { RefreshCw, Clock } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useSampleContext } from '../context/SampleContext'

export default function Header() {
  const { sampleId, refresh } = useSampleContext()
  const [now, setNow] = useState(new Date())
  const [spinning, setSpinning] = useState(false)

  // Update clock every second
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  function handleRefresh() {
    setSpinning(true)
    refresh()
    setTimeout(() => setSpinning(false), 800)
  }

  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  return (
    <header style={{
      height: 48,
      background: '#060d1a',
      borderBottom: '1px solid #0f1d33',
      display: 'flex', alignItems: 'center',
      padding: '0 20px',
      gap: 16,
      flexShrink: 0,
    }}>
      {/* Left: title */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ color: '#c8d8ec', fontSize: '0.82rem', fontWeight: 700 }}>
          AI World Model for Predictive Cyber Defence
        </span>
        <span style={{ color: '#1e3a5f', fontSize: '0.8rem' }}>|</span>
        <span style={{ color: '#2a4060', fontSize: '0.72rem' }}>
          SIH Research Demo
        </span>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Live demo badge */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        padding: '2px 10px',
        background: 'rgba(6,182,212,0.08)',
        border: '1px solid rgba(6,182,212,0.20)',
        borderRadius: 20,
      }}>
        <span className="pulse-dot" style={{
          width: 6, height: 6, borderRadius: '50%',
          background: '#06b6d4', display: 'inline-block',
        }} />
        <span style={{ color: '#06b6d4', fontSize: '0.7rem', fontWeight: 700 }}>LIVE DEMO</span>
        <span style={{ color: '#1e3a5f', margin: '0 3px' }}>·</span>
        <span style={{ color: '#2a5070', fontSize: '0.68rem' }}>SIMULATED TELEMETRY</span>
      </div>

      {/* Sample indicator */}
      <div style={{
        padding: '2px 10px',
        background: '#0a1425',
        border: '1px solid #1a2c4a',
        borderRadius: 5,
        color: '#5d7a9a', fontSize: '0.72rem',
      }}>
        Sample <span style={{ color: '#93c5fd', fontFamily: 'monospace', fontWeight: 700 }}>#{sampleId}</span>
      </div>

      {/* Clock */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        color: '#2a4060', fontSize: '0.72rem',
      }}>
        <Clock size={12} />
        <span style={{ fontFamily: 'monospace', color: '#3d5275' }}>{timeStr}</span>
      </div>

      {/* Refresh */}
      <button
        onClick={handleRefresh}
        title="Refresh all data"
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
          style={{ transition: 'transform 0.4s', transform: spinning ? 'rotate(360deg)' : 'none' }}
        />
        Refresh
      </button>
    </header>
  )
}
