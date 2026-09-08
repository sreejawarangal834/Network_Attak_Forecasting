interface SkeletonProps {
  lines?: number
  height?: number | string
  className?: string
}

function SkeletonLine({ height = 16, width = '100%' }: { height?: number; width?: string }) {
  return (
    <div style={{
      height, width,
      background: 'linear-gradient(90deg, #111e35 25%, #1a2c4a 50%, #111e35 75%)',
      backgroundSize: '400% 100%',
      animation: 'shimmer 1.5s infinite',
      borderRadius: 4,
    }} />
  )
}

export default function LoadingSkeleton({ lines = 3, height = 120 }: SkeletonProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <style>{`
        @keyframes shimmer {
          0%   { background-position: 200% 0 }
          100% { background-position: -200% 0 }
        }
      `}</style>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine key={i} height={typeof height === 'number' ? height / lines : 20}
          width={i === lines - 1 ? '70%' : '100%'} />
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div style={{
      background: '#0d1526', border: '1px solid rgba(255,255,255,0.06)',
      borderRadius: 8, padding: 16,
    }}>
      <LoadingSkeleton lines={4} height={100} />
    </div>
  )
}
