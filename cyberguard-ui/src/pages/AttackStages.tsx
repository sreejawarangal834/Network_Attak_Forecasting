/**
 * AttackStages.tsx — Cyber attack lifecycle visualisation.
 *
 * Consumes: GET /predict/{sample_id}, GET /forecast/{sample_id}
 * Shows: kill-chain pipeline with current/predicted/forecast stages highlighted.
 */

import { useMemo } from 'react'
import { ChevronDown, Info } from 'lucide-react'

import { useSampleContext } from '../context/SampleContext'
import { useApi } from '../hooks/useApi'
import { getPrediction, getForecast } from '../services/api'

import Panel from '../components/Panel'
import MitreBadge from '../components/MitreBadge'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'
import {
  ATTACK_STAGES, STAGE_COLORS, STAGE_ICONS, MITRE_MAP,
  fmtPct, type AttackStageKey,
} from '../utils/constants'

const STAGE_DESCRIPTIONS: Record<AttackStageKey, string> = {
  Benign:             'Normal network behaviour — no threat indicators.',
  Reconnaissance:     'Attacker is scanning hosts and ports to map the network.',
  BruteForce:         'Repeated credential-stuffing or password spray attempts.',
  LateralMovement:    'Attacker moves between internal hosts via SMB/RDP.',
  CommandAndControl:  'Compromised host beacons to an external C2 server.',
}

export default function AttackStages() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])

  const pred     = useApi(() => getPrediction(sampleId), deps)
  const forecast = useApi(() => getForecast(sampleId),   deps)

  // Collect all forecast stages
  const forecastStages = useMemo(() => {
    if (!forecast.data) return new Set<string>()
    return new Set(forecast.data.forecast.map(f => f.stage))
  }, [forecast.data])

  const predictedStage = pred.data?.predicted_stage
  const trueStage      = pred.data?.current_true_stage

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Attack Stages
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Cyber attack lifecycle — stage classification and ATT&CK representative mapping
        </p>
      </div>

      {(pred.error || forecast.error) && !pred.loading && (
        <ErrorState error={pred.error || forecast.error || ''} onRetry={pred.refetch} />
      )}

      {/* Legend */}
      {!pred.loading && pred.data && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          {[
            { color: '#3b82f6', label: 'Predicted stage' },
            { color: '#06b6d4', label: 'In 5-step forecast' },
            { color: '#5d7a9a', label: 'Reference (ground truth)' },
            { color: '#1e3a5f', label: 'Not in forecast' },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
              <span style={{ color: '#3d5275', fontSize: '0.72rem' }}>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Kill-chain pipeline */}
      <Panel title="Kill-Chain Pipeline">
        {pred.loading ? <LoadingSkeleton lines={5} height={280} /> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {ATTACK_STAGES.map((stage, idx) => {
              const isPredicted  = stage === predictedStage
              const isTrueStage  = stage === trueStage
              const inForecast   = forecastStages.has(stage)
              const stageColor   = STAGE_COLORS[stage]
              const mitre        = MITRE_MAP[stage]

              let borderColor = '#1a2c4a'
              let bgColor     = '#070d1a'
              let textOpacity = 0.4

              if (isPredicted)  { borderColor = stageColor; bgColor = `${stageColor}14`; textOpacity = 1 }
              else if (inForecast) { borderColor = '#06b6d466'; bgColor = 'rgba(6,182,212,0.05)'; textOpacity = 0.85 }
              else if (isTrueStage){ borderColor = '#5d7a9a55'; bgColor = '#0d1526'; textOpacity = 0.7 }

              return (
                <div key={stage}>
                  <div style={{
                    border: `1px solid ${borderColor}`,
                    borderLeft: `4px solid ${isPredicted ? stageColor : inForecast ? '#06b6d4' : isTrueStage ? '#5d7a9a' : '#1a2c4a'}`,
                    borderRadius: 8, padding: '12px 16px',
                    background: bgColor,
                    display: 'flex', alignItems: 'center', gap: 14,
                    opacity: textOpacity,
                    transition: 'all 0.2s',
                  }}>
                    {/* Icon + stage */}
                    <div style={{ fontSize: '1.4rem', flexShrink: 0 }}>
                      {STAGE_ICONS[stage]}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
                      }}>
                        <span style={{
                          color: isPredicted ? stageColor : '#c8d8ec',
                          fontSize: '0.92rem', fontWeight: isPredicted ? 800 : 600,
                        }}>
                          {stage}
                        </span>
                        {isPredicted && (
                          <span style={{
                            background: `${stageColor}22`, border: `1px solid ${stageColor}55`,
                            borderRadius: 4, padding: '1px 7px',
                            color: stageColor, fontSize: '0.62rem', fontWeight: 700,
                          }}>
                            PREDICTED
                          </span>
                        )}
                        {isTrueStage && !isPredicted && (
                          <span style={{
                            background: '#5d7a9a18', border: '1px solid #5d7a9a44',
                            borderRadius: 4, padding: '1px 7px',
                            color: '#5d7a9a', fontSize: '0.62rem',
                          }}>
                            REFERENCE
                          </span>
                        )}
                        {inForecast && !isPredicted && (
                          <span style={{
                            background: 'rgba(6,182,212,0.10)', border: '1px solid rgba(6,182,212,0.25)',
                            borderRadius: 4, padding: '1px 7px',
                            color: '#06b6d4', fontSize: '0.62rem',
                          }}>
                            IN FORECAST
                          </span>
                        )}
                      </div>
                      <div style={{ color: '#3d5275', fontSize: '0.75rem', marginTop: 3 }}>
                        {STAGE_DESCRIPTIONS[stage]}
                      </div>
                    </div>

                    {/* MITRE + confidence */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end', flexShrink: 0 }}>
                      {mitre
                        ? <MitreBadge id={mitre.id} name={mitre.name} size="sm" />
                        : <span style={{ color: '#1e3a5f', fontSize: '0.68rem' }}>No MITRE mapping</span>
                      }
                      {isPredicted && pred.data && (
                        <span style={{ color: '#5d7a9a', fontSize: '0.7rem' }}>
                          conf: {fmtPct(pred.data.stage_confidence)}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Connector arrow */}
                  {idx < ATTACK_STAGES.length - 1 && (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0' }}>
                      <ChevronDown size={14} color="#1e3a5f" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Panel>

      {/* Forecast stage sequence */}
      {forecast.data && (
        <Panel
          title="Predicted Stage Sequence"
          subtitle="Stages as forecast across the 5-step autoregressive horizon"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {forecast.data.forecast.map((step, i) => {
              const c = STAGE_COLORS[step.stage as AttackStageKey] ?? '#7d95b5'
              return (
                <div key={step.step} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    background: `${c}14`, border: `1px solid ${c}44`,
                    borderRadius: 7, padding: '8px 14px', textAlign: 'center',
                  }}>
                    <div style={{ color: '#3d5275', fontSize: '0.62rem', marginBottom: 4 }}>
                      T+{step.step}
                    </div>
                    <div style={{ color: c, fontSize: '0.82rem', fontWeight: 700 }}>
                      {STAGE_ICONS[step.stage as AttackStageKey]} {step.stage}
                    </div>
                    <div style={{ color: '#2a4060', fontSize: '0.65rem', marginTop: 3 }}>
                      {fmtPct(step.attack_probability)}
                    </div>
                  </div>
                  {i < forecast.data!.forecast.length - 1 && (
                    <span style={{ color: '#1e3a5f', fontSize: '1rem' }}>→</span>
                  )}
                </div>
              )
            })}
          </div>
        </Panel>
      )}

      {/* MITRE disclaimer */}
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 8,
        padding: '10px 14px',
        background: 'rgba(59,130,246,0.04)',
        border: '1px solid rgba(59,130,246,0.12)',
        borderRadius: 7, color: '#2a5070', fontSize: '0.72rem',
      }}>
        <Info size={13} style={{ marginTop: 1, flexShrink: 0, color: '#3b82f6' }} />
        <div>
          <strong style={{ color: '#5d7a9a' }}>MITRE ATT&CK Disclaimer:</strong>{' '}
          The mappings shown (Reconnaissance → T1595, BruteForce → T1110, etc.) are
          prototype stage-to-technique assignments for demonstration. The model predicts
          network-state attack stages; it does not directly detect ATT&CK techniques.
        </div>
      </div>
    </div>
  )
}
