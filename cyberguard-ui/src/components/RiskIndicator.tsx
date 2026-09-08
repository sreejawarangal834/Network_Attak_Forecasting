import { getRiskLevel, fmtPct } from '../utils/constants'

interface RiskIndicatorProps {
  probability: number
  showLabel?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export default function RiskIndicator({
  probability, showLabel = true, size = 'md',
}: RiskIndicatorProps) {
  const risk = getRiskLevel(probability)
  const pct  = fmtPct(probability)

  const barH   = size === 'sm' ? 4  : size === 'lg' ? 8  : 6
  const valSize = size === 'sm' ? '1rem' : size === 'lg' ? '1.8rem' : '1.4rem'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <span style={{ color: risk.color, fontSize: valSize, fontWeight: 800 }}>
            {pct}
          </span>
          <span style={{
            color: risk.color,
            fontSize: '0.68rem', fontWeight: 700,
            background: `${risk.color}18`,
            border: `1px solid ${risk.color}44`,
            borderRadius: 4,
            padding: '1px 7px',
          }}>
            {risk.label}
          </span>
        </div>
      )}
      {/* Track */}
      <div style={{
        height: barH, borderRadius: barH, background: '#1a2c4a', overflow: 'hidden',
      }}>
        {/* Fill */}
        <div style={{
          height: '100%',
          width: `${probability * 100}%`,
          background: `linear-gradient(90deg, ${risk.color}88, ${risk.color})`,
          borderRadius: barH,
          transition: 'width 0.5s ease',
        }} />
      </div>
      {/* Threshold markers */}
      <div style={{ position: 'relative', height: 12 }}>
        {[30, 70].map(pctMark => (
          <div key={pctMark} style={{
            position: 'absolute', left: `${pctMark}%`,
            top: 0, width: 1, height: 8, background: '#2a4060',
          }}>
            <span style={{
              position: 'absolute', top: 8, left: -8,
              fontSize: '0.58rem', color: '#3d5275',
            }}>
              {pctMark}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
