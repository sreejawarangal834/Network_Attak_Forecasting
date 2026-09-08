/**
 * NetworkState.tsx — Predicted network feature state viewer.
 *
 * Consumes: GET /forecast/{sample_id}/states
 * 44 features per step — shown in searchable table + bar chart.
 */

import { useMemo, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { Search } from 'lucide-react'

import { useSampleContext } from '../context/SampleContext'
import { useApi } from '../hooks/useApi'
import { getForecastStates } from '../services/api'

import Panel from '../components/Panel'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ErrorState from '../components/ErrorState'

export default function NetworkState() {
  const { sampleId, refreshToken } = useSampleContext()
  const deps   = useMemo(() => [sampleId, refreshToken], [sampleId, refreshToken])
  const states = useApi(() => getForecastStates(sampleId), deps)

  const [selectedStep, setSelectedStep] = useState(1)
  const [search, setSearch]             = useState('')
  const [topN, setTopN]                 = useState(10)

  // Current step's features
  const currentState = useMemo(() => {
    if (!states.data) return null
    return states.data.find(s => s.step === selectedStep) ?? states.data[0]
  }, [states.data, selectedStep])

  // Filtered feature list
  const filteredFeatures = useMemo(() => {
    if (!currentState) return []
    return Object.entries(currentState.features)
      .filter(([name]) => name.toLowerCase().includes(search.toLowerCase()))
      .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
  }, [currentState, search])

  // Top-N for chart
  const chartData = useMemo(() => {
    return filteredFeatures.slice(0, topN).map(([name, value]) => ({
      name: name.length > 22 ? name.slice(0, 20) + '…' : name,
      fullName: name,
      value: parseFloat(value.toFixed(4)),
    }))
  }, [filteredFeatures, topN])

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div>
        <h1 style={{ color: '#c8d8ec', fontSize: '1.15rem', fontWeight: 700, margin: '0 0 4px' }}>
          Network State
        </h1>
        <p style={{ color: '#3d5275', fontSize: '0.78rem', margin: 0 }}>
          Predicted 44-feature network state vectors for each forecast step
        </p>
      </div>

      {states.error && !states.loading && (
        <ErrorState error={states.error} onRetry={states.refetch} />
      )}

      {/* Step selector */}
      <Panel title="Forecast Step">
        {states.loading ? <LoadingSkeleton lines={2} height={48} /> : states.data ? (
          <div style={{ display: 'flex', gap: 8 }}>
            {states.data.map(s => (
              <button
                key={s.step}
                onClick={() => setSelectedStep(s.step)}
                style={{
                  padding: '7px 18px',
                  background: selectedStep === s.step ? '#1d4ed8' : '#070d1a',
                  border: `1px solid ${selectedStep === s.step ? '#3b82f6' : '#1a2c4a'}`,
                  borderRadius: 6, color: selectedStep === s.step ? '#fff' : '#4d6a8a',
                  fontSize: '0.82rem', fontWeight: selectedStep === s.step ? 700 : 500,
                  cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                Step {s.step}
              </button>
            ))}
            <div style={{
              marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6,
              color: '#3d5275', fontSize: '0.72rem',
            }}>
              Features: {currentState ? Object.keys(currentState.features).length : '—'}
            </div>
          </div>
        ) : null}
      </Panel>

      {/* Chart + table */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Bar chart — top N features */}
        <Panel
          title={`Top ${topN} Feature Values — Step ${selectedStep}`}
          action={
            <select
              value={topN}
              onChange={e => setTopN(Number(e.target.value))}
              style={{
                background: '#070d1a', border: '1px solid #1a2c4a',
                borderRadius: 5, color: '#5d7a9a', fontSize: '0.72rem', padding: '3px 6px',
              }}
            >
              {[5, 10, 15, 20].map(n => (
                <option key={n} value={n}>Top {n}</option>
              ))}
            </select>
          }
        >
          {states.loading ? <LoadingSkeleton lines={5} height={260} /> :
           currentState ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#3d5275', fontSize: 10 }} />
                <YAxis
                  type="category" dataKey="name" width={110}
                  tick={{ fill: '#5d7a9a', fontSize: 10 }}
                />
                <Tooltip
                  contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.75rem' }}
                  formatter={(v: unknown, _: unknown, props: { payload?: { fullName: string } }) => [
                    (typeof v === 'number' ? v : 0).toFixed(4), props.payload?.fullName ?? '',
                  ] as [string, string]}
                />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : null}
        </Panel>

        {/* Searchable feature table */}
        <Panel
          title="All Features"
          action={
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Search size={13} color="#3d5275" />
              <input
                type="text"
                placeholder="Search features…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  background: '#070d1a', border: '1px solid #1a2c4a',
                  borderRadius: 5, color: '#e2e8f0', fontSize: '0.75rem',
                  padding: '4px 8px', outline: 'none', width: 140,
                }}
              />
            </div>
          }
        >
          {states.loading ? <LoadingSkeleton lines={8} height={260} /> :
           currentState ? (
            <div style={{ height: 260, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                <thead style={{ position: 'sticky', top: 0, background: '#0d1526' }}>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '5px 8px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', borderBottom: '1px solid #1a2c4a' }}>
                      Feature
                    </th>
                    <th style={{ textAlign: 'right', padding: '5px 8px', color: '#3d5275', fontSize: '0.65rem', textTransform: 'uppercase', borderBottom: '1px solid #1a2c4a' }}>
                      Value
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFeatures.map(([name, value], i) => (
                    <tr key={name} style={{ background: i % 2 === 0 ? 'transparent' : '#070d1a' }}>
                      <td style={{ padding: '5px 8px', color: '#7d95b5', fontFamily: 'monospace', fontSize: '0.73rem' }}>
                        {name}
                      </td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', color: '#c8d8ec', fontFamily: 'monospace' }}>
                        {value.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                  {filteredFeatures.length === 0 && (
                    <tr>
                      <td colSpan={2} style={{ padding: '20px 8px', textAlign: 'center', color: '#1e3a5f' }}>
                        No features match "{search}"
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : null}
        </Panel>
      </div>

      {/* Cross-step comparison */}
      {states.data && !states.loading && (
        <Panel
          title="Feature Comparison Across Steps"
          subtitle="Select a feature to compare its value across the 5 predicted steps"
        >
          <CrossStepComparison states={states.data} />
        </Panel>
      )}
    </div>
  )
}

function CrossStepComparison({ states }: { states: import('../types/api').ForecastStatesResponse }) {
  const allFeatures = useMemo(() => {
    if (!states.length) return []
    return Object.keys(states[0].features).sort()
  }, [states])

  const [feature, setFeature] = useState(allFeatures[0] ?? '')

  const chartData = useMemo(() => {
    return states.map(s => ({
      name: `Step ${s.step}`,
      value: parseFloat((s.features[feature] ?? 0).toFixed(4)),
    }))
  }, [states, feature])

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: '#3d5275', fontSize: '0.75rem' }}>Feature:</span>
        <select
          value={feature}
          onChange={e => setFeature(e.target.value)}
          style={{
            background: '#070d1a', border: '1px solid #1a2c4a',
            borderRadius: 5, color: '#c8d8ec', fontSize: '0.78rem',
            padding: '5px 8px', maxWidth: 280,
          }}
        >
          {allFeatures.map(f => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#0f1d33" />
          <XAxis dataKey="name" tick={{ fill: '#3d5275', fontSize: 11 }} />
          <YAxis tick={{ fill: '#3d5275', fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: '#0d1526', border: '1px solid #1a2c4a', borderRadius: 6, fontSize: '0.78rem' }}
          />
          <Bar dataKey="value" fill="#06b6d4" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
