import { AlertTriangle, RefreshCw, WifiOff } from 'lucide-react'

interface ErrorStateProps {
  error: string
  onRetry?: () => void
  compact?: boolean
}

function isOfflineError(err: string) {
  return err.toLowerCase().includes('unable to reach') ||
    err.toLowerCase().includes('failed to fetch') ||
    err.toLowerCase().includes('network')
}

export default function ErrorState({ error, onRetry, compact = false }: ErrorStateProps) {
  const offline = isOfflineError(error)

  if (compact) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px',
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.25)',
        borderRadius: 6,
        color: '#ef4444', fontSize: '0.8rem',
      }}>
        <AlertTriangle size={14} />
        <span>{error}</span>
        {onRetry && (
          <button onClick={onRetry} style={{
            marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4,
            background: 'none', border: 'none', color: '#ef4444',
            cursor: 'pointer', fontSize: '0.75rem',
          }}>
            <RefreshCw size={12} /> Retry
          </button>
        )}
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', gap: 16,
      padding: 48,
      background: '#0d1526',
      border: '1px solid rgba(239,68,68,0.2)',
      borderRadius: 10,
      textAlign: 'center',
    }}>
      {offline
        ? <WifiOff size={40} color="#ef4444" style={{ opacity: 0.6 }} />
        : <AlertTriangle size={40} color="#ef4444" style={{ opacity: 0.6 }} />}

      <div>
        <div style={{ color: '#f1f5f9', fontSize: '1rem', fontWeight: 600, marginBottom: 6 }}>
          {offline ? 'Backend Offline' : 'Request Failed'}
        </div>
        <div style={{ color: '#5d7a9a', fontSize: '0.82rem', maxWidth: 380 }}>
          {offline
            ? 'Unable to connect to the World Model API. Make sure FastAPI is running on port 8000.'
            : error}
        </div>
        {offline && (
          <div style={{
            marginTop: 12, padding: '6px 12px',
            background: '#111e35', borderRadius: 5,
            fontFamily: 'monospace', fontSize: '0.75rem', color: '#7d95b5',
            display: 'inline-block',
          }}>
            python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
          </div>
        )}
      </div>

      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 20px',
            background: '#1d4ed8', border: 'none', borderRadius: 6,
            color: '#fff', fontSize: '0.82rem', fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  )
}
