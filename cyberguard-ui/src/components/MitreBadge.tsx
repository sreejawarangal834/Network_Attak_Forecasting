interface MitreBadgeProps {
  id: string
  name: string
  size?: 'sm' | 'md'
}

export default function MitreBadge({ id, name, size = 'md' }: MitreBadgeProps) {
  const fontSize = size === 'sm' ? '0.65rem' : '0.72rem'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: 'rgba(59,130,246,0.10)',
      border: '1px solid rgba(59,130,246,0.30)',
      borderRadius: 5,
      padding: size === 'sm' ? '1px 7px' : '2px 10px',
      fontSize,
      fontWeight: 600,
      color: '#60a5fa',
      whiteSpace: 'nowrap',
    }}>
      <span style={{ fontFamily: 'monospace', color: '#93c5fd' }}>{id}</span>
      <span style={{ color: '#7d95b5' }}>·</span>
      <span>{name}</span>
    </span>
  )
}
