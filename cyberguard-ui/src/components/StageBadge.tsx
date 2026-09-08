import { STAGE_COLORS, STAGE_ICONS, type AttackStageKey } from '../utils/constants'

interface StageBadgeProps {
  stage: string
  size?: 'sm' | 'md' | 'lg'
  showIcon?: boolean
}

export default function StageBadge({ stage, size = 'md', showIcon = true }: StageBadgeProps) {
  const color = STAGE_COLORS[stage as AttackStageKey] ?? '#7d95b5'
  const icon  = STAGE_ICONS[stage as AttackStageKey] ?? '●'

  const fontSize = size === 'sm' ? '0.68rem' : size === 'lg' ? '0.9rem' : '0.75rem'
  const padding  = size === 'sm' ? '1px 7px' : size === 'lg' ? '4px 14px' : '2px 10px'

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: `${color}18`,
      border: `1px solid ${color}44`,
      borderRadius: 6,
      padding,
      fontSize,
      fontWeight: 600,
      color,
      whiteSpace: 'nowrap',
    }}>
      {showIcon && <span style={{ fontSize: '0.85em' }}>{icon}</span>}
      {stage}
    </span>
  )
}
