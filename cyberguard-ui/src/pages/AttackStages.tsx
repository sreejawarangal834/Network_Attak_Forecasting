/**
 * AttackStages.tsx — Cyber attack lifecycle visualisation.
 *
 * PRIMARY MODE (uploaded analysis in AnalysisContext):
 *   Data: analysis.current_state + analysis.forecast from context.
 *   Shows kill-chain with predicted / in-forecast stages highlighted.
 *   Clearly labelled NETWORK-LEVEL PREDICTION throughout.
 *   If an entity is selected, shows it as the observed endpoint
 *   but prediction scope remains network-level.
 *
 * FALLBACK MODE (no analysis):
 *   Upload prompt + Developer/Demo section (GET /predict + /forecast).
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, Info, UploadCloud } from 'lucide-react'

import { useAnalysisContext } from '../context/AnalysisContext'
import { useSampleContext }   from '../context/SampleContext'
import { useApi }             from '../hooks/useApi'
import { getPrediction, getForecast } from '../services/api'

import Panel      from '../components/Panel'
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

// ─────────────────────────────────────────────────────────────────────────────
// Shared kill-chain renderer
// ─────────────────────────────────────────────────────────────────────────────

interface KillChainProps {
  predictedStage:   string | undefined
  forecastStages:   Set<string>
  stageConf:        number | undefined
  referenceStage?:  string        // ground-truth stage (demo mode only)
  isNetworkLevel:   boolean
}

function KillChain({ predictedStage, forecastStages, stageConf, referenceStage, isNetworkLevel }: KillChainProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {isNetworkLevel && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6, marginBottom: 6 }}>
          <Info size={12} color="#3b82f6" />
          <span style={{ color: '#5d7a9a', fontSize: '0.72rem' }}>
            <strong style={{ color: '#93c5fd' }}>NETWORK-LEVEL PREDICTION</strong> — stage reflects aggregate network state, not individual device behaviour.
          </span>
        </div>
      )}

      {ATTACK_STAGES.map((stage, idx) => {
        const isPredicted  = stage === predictedStage
        const inForecast   = forecastStages.has(stage)
        const isRef        = referenceStage && stage === referenceStage && !isPredicted
        const stageColor   = STAGE_COLORS[stage]
        const mitre        = MITRE_MAP[stage]

        let borderColor = '#1a2c4a', bgColor = '#070d1a', textOpacity = 0.4
        if (isPredicted)  { borderColor = stageColor; bgColor = `${stageColor}14`; textOpacity = 1 }
        else if (inForecast) { borderColor = '#06b6d466'; bgColor = 'rgba(6,182,212,0.05)'; textOpacity = 0.85 }
        else if (isRef)   { borderColor = '#5d7a9a55'; bgColor = '#0d1526'; textOpacity = 0.7 }

        return (
          <div key={stage}>
            <div style={{
              border: `1px solid ${borderColor}`,
              borderLeft: `4px solid ${isPredicted ? stageColor : inForecast ? '#06b6d4' : isRef ? '#5d7a9a' : '#1a2c4a'}`,
              borderRadius: 8, padding: '12px 16px', background: bgColor,
              display: 'flex', alignItems: 'center', gap: 14, opacity: textOpacity, transition: 'all 0.2s',
            }}>
              <div style={{ fontSize: '1.4rem', flexShrink: 0 }}>{STAGE_ICONS[stage]}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ color: isPredicted ? stageColor : '#c8d8ec', fontSize: '0.92rem', fontWeight: isPredicted ? 800 : 600 }}>{stage}</span>
                  {isPredicted && <span style={{ background: `${stageColor}22`, border: `1px solid ${stageColor}55`, borderRadius: 4, padding: '1px 7px', color: stageColor, fontSize: '0.62rem', fontWeight: 700 }}>PREDICTED</span>}
                  {isPredicted && isNetworkLevel && <span style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: 4, padding: '1px 7px', color: '#60a5fa', fontSize: '0.62rem' }}>NETWORK-LEVEL</span>}
                  {isRef && <span style={{ background: '#5d7a9a18', border: '1px solid #5d7a9a44', borderRadius: 4, padding: '1px 7px', color: '#5d7a9a', fontSize: '0.62rem' }}>REFERENCE</span>}
                  {inForecast && !isPredicted && <span style={{ background: 'rgba(6,182,212,0.10)', border: '1px solid rgba(6,182,212,0.25)', borderRadius: 4, padding: '1px 7px', color: '#06b6d4', fontSize: '0.62rem' }}>IN FORECAST</span>}
                </div>
                <div style={{ color: '#3d5275', fontSize: '0.75rem', marginTop: 3 }}>{STAGE_DESCRIPTIONS[stage]}</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5, alignItems: 'flex-end', flexShrink: 0 }}>
                {mitre ? <MitreBadge id={mitre.id} name={mitre.name} size="sm" /> : <span style={{ color: '#1e3a5f', fontSize: '0.68rem' }}>No MITRE mapping</span>}
                {isPredicted && stageConf !== undefined && (
                  <span style={{ color: '#5d7a9a', fontSize: '0.7rem' }}>conf: {fmtPct(stageConf)}</span>
                )}
              </div>
            </div>
            {idx < ATTACK_STAGES.length - 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0' }}>
                <span style={{ color: '#1e3a5f', fontSize: '0.85rem' }}>↓</span>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Primary view — analysis context
// ─────────────────────────────────────────────────────────────────────────────

function AnalysisStagesView() {
  const { analysis, selectedEntity, entitiesData } = useAnalysisContext()

  const cs = analysis?.current_state
  const forecast = analysis?.forecast ?? []

  const predictedStage = cs?.stage
  const stageConf      = cs?.stage_confidence
  const forecastStages = useMemo(() => new Set(forecast.map(f => f.stage)), [forecast])

  const hasEntityIds   = entitiesData?.has_entity_ids ?? false
  const observedLabel  = selectedEntity?.entity_id

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Observed endpoint notice */}
      {hasEntityIds && observedLabel && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 7 }}>
          <Info size={14} color="#818cf8" style={{ flexShrink: 0 }} />
          <div style={{ color: '#a5b4fc', fontSize: '0.78rem' }}>
            <strong>Observed endpoint:</strong> {observedLabel}
            <span style={{ color: '#4d5b79', marginLeft: 8 }}>
              — prediction reflects aggregate network state, not this device individually
            </span>
          </div>
        </div>
      )}

      {/* Current state strip */}
      {cs && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {[
            { label: 'Predicted Stage',  value: cs.stage },
            { label: 'Attack Prob.',     value: fmtPct(cs.attack_probability) },
            { label: 'Stage Confidence', value: fmtPct(cs.stage_confidence) },
            { label: 'MITRE',            value: cs.mitre_attack_id ?? '—' },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: '#070d1a', border: '1px solid #1a2c4a', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
              <div style={{ color: '#c8d8ec', fontSize: '0.85rem', fontWeight: 600 }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Kill chain */}
      <Panel title="Kill-Chain Pipeline">
        <KillChain
          predictedStage={predictedStage}
          forecastStages={forecastStages}
          stageConf={stageConf}
          isNetworkLevel
        />
      </Panel>

      {/* Forecast stage sequence */}
      {forecast.length > 0 && (
        <Panel title="Predicted Stage Sequence" subtitle="Stages across the 5-step autoregressive horizon — NETWORK-LEVEL">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {forecast.map((f, i) => {
              const c = STAGE_COLORS[f.stage as AttackStageKey] ?? '#7d95b5'
              return (
                <div key={f.step} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ background: `${c}14`, border: `1px solid ${c}44`, borderRadius: 7, padding: '8px 14px', textAlign: 'center' }}>
                    <div style={{ color: '#3d5275', fontSize: '0.62rem', marginBottom: 4 }}>+{f.step * 10}s</div>
                    <div style={{ color: c, fontSize: '0.82rem', fontWeight: 700 }}>{STAGE_ICONS[f.stage as AttackStageKey]} {f.stage}</div>
                    <div style={{ color: '#2a4060', fontSize: '0.65rem', marginTop: 3 }}>{fmtPct(f.attack_probability)}</div>
                  </div>
                  {i < forecast.length - 1 && <span style={{ color: '#1e3a5f', fontSize: '1rem' }}>→</span>}
                </div>
              )
            })}
          </div>
          <div style={{ marginTop: 10, color: '#1e3a5f', fontSize: '0.65rem' }}>
            Prediction scope: network-level. MITRE mappings are prototype stage-to-technique assignments.
          </div>
        </Panel>
      )}

      {/* MITRE panel */}
      {cs?.mitre_attack_id && (
        <Panel title="MITRE ATT&CK">
          <MitreBadge id={cs.mitre_attack_id} name={cs.mitre_attack_name ?? ''} />
          <div style={{ marginTop: 8, color: '#1e3a5f', fontSize: '0.65rem' }}>
            Representative stage-to-technique mapping — not direct ATT&CK technique detection.
          </div>
        </Panel>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Dev/demo fallback
// ─────────────────────────────────────────────────────────────────────────────

function DemoStagesView() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])

  const pred     = useApi(() => getPrediction(sampleId), deps)
  const forecast = useApi(() => getForecast(sampleId),   deps)

  const forecastStages = useMemo(() => {
    if (!forecast.data) return new Set<string>()
    return new Set(forecast.data.forecast.map(f => f.stage))
  }, [forecast.data])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: 6 }}>
        <Info size={13} color="#3b82f6" />
        <span style={{ color: '#5d7a9a', fontSize: '0.75rem' }}>
          <strong style={{ color: '#93c5fd' }}>Developer / Demo mode</strong> — Sample #{sampleId}.
        </span>
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

      <Panel title="Kill-Chain Pipeline">
        {pred.loading ? <LoadingSkeleton lines={5} height={280} /> : (
          <KillChain
            predictedStage={pred.data?.predicted_stage}
            forecastStages={forecastStages}
            stageConf={pred.data?.stage_confidence}
            referenceStage={pred.data?.current_true_stage}
            isNetworkLevel={false}
          />
        )}
      </Panel>

      {forecast.data && (
        <Panel title="Predicted Stage Sequence" subtitle="5-step autoregressive horizon">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            {forecast.data.forecast.map((f, i) => {
              const c = STAGE_COLORS[f.stage as AttackStageKey] ?? '#7d95b5'
              return (
                <div key={f.step} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ background: `${c}14`, border: `1px solid ${c}44`, borderRadius: 7, padding: '8px 14px', textAlign: 'center' }}>
                    <div style={{ color: '#3d5275', fontSize: '0.62rem', marginBottom: 4 }}>T+{f.step}</div>
                    <div style={{ color: c, fontSize: '0.82rem', fontWeight: 700 }}>{STAGE_ICONS[f.stage as AttackStageKey]} {f.stage}</div>
                    <div style={{ color: '#2a4060', fontSize: '0.65rem', marginTop: 3 }}>{fmtPct(f.attack_probability)}</div>
                  </div>
                  {i < forecast.data!.forecast.length - 1 && <span style={{ color: '#1e3a5f', fontSize: '1rem' }}>→</span>}
                </div>
              )
            })}
          </div>
        </Panel>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Root component
// ─────────────────────────────────────────────────────────────────────────────

export default function AttackStages() {
  const { hasAnalysis, isRestoring, restoreStatus } = useAnalysisContext()
  const [demoOpen, setDemoOpen] = useState(false)

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>Attack Stages</h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Cyber attack lifecycle — stage classification and ATT&CK representative mapping
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '8px 14px', background: 'rgba(59,130,246,0.04)', border: '1px solid rgba(59,130,246,0.12)', borderRadius: 7, color: '#2a5070', fontSize: '0.72rem' }}>
        <Info size={13} style={{ marginTop: 1, flexShrink: 0, color: '#3b82f6' }} />
        MITRE ATT&CK mappings are prototype stage-to-technique assignments. The model predicts network-state attack stages; it does not directly detect ATT&CK techniques.
      </div>

      {isRestoring && <LoadingSkeleton lines={5} height={280} />}

      {!isRestoring && restoreStatus === 'expired' && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '36px 24px', background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: 12, textAlign: 'center' }}>
          <div style={{ color: '#f59e0b', fontSize: '1rem', fontWeight: 700 }}>Previous Analysis Unavailable</div>
          <div style={{ color: '#927a5a', fontSize: '0.82rem' }}>The backend was restarted. Please re-upload your telemetry.</div>
          <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
            <UploadCloud size={14} /> Upload New Telemetry
          </Link>
        </div>
      )}

      {!isRestoring && restoreStatus !== 'expired' && (
        hasAnalysis ? (
          <>
            <AnalysisStagesView />
            <div style={{ borderTop: '1px solid #0f1d33', paddingTop: 8 }}>
              <button onClick={() => setDemoOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', cursor: 'pointer', color: '#1e3a5f', fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', padding: '4px 0' }}>
                <ChevronDown size={12} style={{ transform: demoOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                Developer / Demo View
              </button>
              {demoOpen && <div style={{ marginTop: 10 }}><DemoStagesView /></div>}
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '48px 24px', background: '#0b1526', border: '1px dashed #1a2c4a', borderRadius: 12, textAlign: 'center' }}>
              <UploadCloud size={44} color="#1e3a5f" />
              <div>
                <div style={{ color: '#c8d8ec', fontSize: '1rem', fontWeight: 700, marginBottom: 6 }}>No Analysis Loaded</div>
                <div style={{ color: '#3d5275', fontSize: '0.82rem', maxWidth: 400 }}>Upload network telemetry to view the attack stage classification.</div>
              </div>
              <Link to="/upload" style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 20px', background: '#1d4ed8', borderRadius: 7, color: '#fff', fontSize: '0.85rem', fontWeight: 600, textDecoration: 'none' }}>
                <UploadCloud size={14} /> Upload Telemetry
              </Link>
            </div>
            <Panel title="Developer / Demo View" subtitle="Pre-built test set — not the primary product view">
              <DemoStagesView />
            </Panel>
          </div>
        )
      )}
    </div>
  )
}
