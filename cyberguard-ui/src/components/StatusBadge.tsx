interface StatusBadgeProps {
  status: 'online' | 'offline' | 'warning' | 'demo' | string
  label?: string
  pulse?: boolean
}

const STATUS_CONFIG = {
  online:  { color: '#22c55e', bg: 'rgba(34,197,94,0.12)',  dot: true },
  offline: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)',  dot: false },
  warning: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', dot: false },
  demo:    { color: '#06b6d4', bg: 'rgba(6,182,212,0.12)',  dot: true },
}

export default function StatusBadge({ status, label, pulse = false }: StatusBadgeProps) {
  const cfg = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG]
    ?? { color: '#7d95b5', bg: 'rgba(125,149,181,0.12)', dot: false }

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: cfg.bg,
      border: `1px solid ${cfg.color}44`,
      borderRadius: 20,
      padding: '2px 10px',
      fontSize: '0.72rem',
      fontWeight: 600,
      color: cfg.color,
    }}>
      {cfg.dot && (
        <span
          className={pulse ? 'pulse-dot' : ''}
          style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.color, display: 'inline-block' }}
        />
      )}
      {label ?? status.toUpperCase()}
    </span>
  )
}
