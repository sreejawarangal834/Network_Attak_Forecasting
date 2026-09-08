import type { ReactNode } from 'react'

interface MetricCardProps {
  label: string
  value: string | ReactNode
  sub?: string
  accentColor?: string
  icon?: ReactNode
  className?: string
}

export default function MetricCard({
  label, value, sub, accentColor = '#3b82f6', icon, className = '',
}: MetricCardProps) {
  return (
    <div
      className={`relative rounded-lg p-4 flex flex-col gap-1 overflow-hidden ${className}`}
      style={{
        background: '#0d1526',
        border: `1px solid rgba(255,255,255,0.06)`,
        borderTop: `3px solid ${accentColor}`,
      }}
    >
      <div className="flex items-center justify-between">
        <span style={{ color: '#5d7a9a', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>
          {label}
        </span>
        {icon && <span style={{ color: accentColor, opacity: 0.7 }}>{icon}</span>}
      </div>
      <div style={{ color: accentColor, fontSize: '1.6rem', fontWeight: 800, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ color: '#3d5275', fontSize: '0.72rem' }}>{sub}</div>
      )}
    </div>
  )
}
