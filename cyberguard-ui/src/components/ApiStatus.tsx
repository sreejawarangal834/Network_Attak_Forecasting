import { useEffect, useState } from 'react'
import { getHealth } from '../services/api'

type ConnStatus = 'checking' | 'online' | 'offline'

export default function ApiStatus() {
  const [status, setStatus] = useState<ConnStatus>('checking')

  function check() {
    setStatus('checking')
    getHealth()
      .then(() => setStatus('online'))
      .catch(() => setStatus('offline'))
  }

  useEffect(() => { check() }, [])

  const cfg = {
    checking: { color: '#f59e0b', label: 'Checking…', dot: false },
    online:   { color: '#22c55e', label: 'Backend Connected', dot: true },
    offline:  { color: '#ef4444', label: 'Backend Offline', dot: false },
  }[status]

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '6px 10px',
      background: `${cfg.color}10`,
      border: `1px solid ${cfg.color}33`,
      borderRadius: 6,
      cursor: status !== 'checking' ? 'pointer' : 'default',
    }} onClick={status !== 'checking' ? check : undefined}
       title={status !== 'checking' ? 'Click to recheck' : undefined}>
      {cfg.dot && (
        <span className="pulse-dot" style={{
          width: 7, height: 7, borderRadius: '50%',
          background: cfg.color, display: 'inline-block', flexShrink: 0,
        }} />
      )}
      <span style={{ color: cfg.color, fontSize: '0.72rem', fontWeight: 600 }}>
        {cfg.label}
      </span>
    </div>
  )
}
