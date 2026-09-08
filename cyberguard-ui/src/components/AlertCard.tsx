/**
 * AlertCard.tsx — Demo alert component.
 *
 * IMPORTANT: This is a frontend-generated DEMO alert based on the model's
 * attack probability prediction. The backend does not expose a device-level
 * risk endpoint. This component does NOT claim specific IPs are compromised.
 *
 * When a real /devices or /risk/devices API is added, replace the props here.
 */

import { AlertTriangle, Info } from 'lucide-react'
import StageBadge from './StageBadge'
import MitreBadge from './MitreBadge'
import { getRiskLevel, fmtPct } from '../utils/constants'

interface AlertCardProps {
  attackProbability: number
  predictedStage: string
  mitreId: string
  mitreName: string
  sampleId: number
}

export default function AlertCard({
  attackProbability, predictedStage, mitreId, mitreName, sampleId,
}: AlertCardProps) {
  const risk = getRiskLevel(attackProbability)

  return (
    <div style={{
      background: '#0d1526',
      border: `1px solid ${risk.color}33`,
      borderLeft: `4px solid ${risk.color}`,
      borderRadius: 8, padding: '14px 16px',
    }}>
      {/* Demo label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <AlertTriangle size={14} color={risk.color} />
        <span style={{
          color: risk.color, fontSize: '0.72rem', fontWeight: 700,
          textTransform: 'uppercase', letterSpacing: '0.06em',
        }}>
          MODEL-GENERATED ALERT — DEMO
        </span>
        <span style={{
          marginLeft: 'auto', color: '#3d5275', fontSize: '0.65rem',
          fontFamily: 'monospace',
        }}>
          Sample #{sampleId}
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', marginBottom: 10 }}>
        <div style={{ color: risk.color, fontSize: '1.4rem', fontWeight: 800 }}>
          {fmtPct(attackProbability)}
        </div>
        <div style={{
          background: `${risk.color}18`, border: `1px solid ${risk.color}44`,
          borderRadius: 4, padding: '2px 8px',
          color: risk.color, fontSize: '0.72rem', fontWeight: 700,
        }}>
          {risk.label} RISK
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>Predicted Stage:</span>
        <StageBadge stage={predictedStage} size="sm" />
        <MitreBadge id={mitreId} name={mitreName} size="sm" />
      </div>

      {/* Caveat */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 5,
        marginTop: 10, padding: '6px 10px',
        background: 'rgba(125,149,181,0.06)',
        borderRadius: 5, color: '#3d5275', fontSize: '0.7rem',
      }}>
        <Info size={11} style={{ flexShrink: 0, marginTop: 1 }} />
        Alert generated from model forecast. Source: simulated temporal telemetry.
        This is not a claim of actual device compromise.
      </div>
    </div>
  )
}
