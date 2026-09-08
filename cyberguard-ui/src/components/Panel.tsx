import type { ReactNode } from 'react'

interface PanelProps {
  title?: string
  subtitle?: string
  children: ReactNode
  action?: ReactNode
  className?: string
  style?: React.CSSProperties
}

export default function Panel({ title, subtitle, children, action, style }: PanelProps) {
  return (
    <div style={{
      background: '#0d1526',
      border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 10,
      ...style,
    }}>
      {(title || action) && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid rgba(255,255,255,0.05)',
        }}>
          <div>
            {title && (
              <div style={{ color: '#c8d8ec', fontSize: '0.85rem', fontWeight: 700 }}>
                {title}
              </div>
            )}
            {subtitle && (
              <div style={{ color: '#3d5275', fontSize: '0.7rem', marginTop: 2 }}>
                {subtitle}
              </div>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      <div style={{ padding: 16 }}>
        {children}
      </div>
    </div>
  )
}
