import { useState, useEffect } from 'react'
import { Search } from 'lucide-react'
import { useSampleContext } from '../context/SampleContext'
import { getSamples } from '../services/api'

export default function SampleSelector() {
  const { sampleId, setSampleId, setMaxSamples, maxSamples } = useSampleContext()
  const [inputVal, setInputVal] = useState(String(sampleId))
  const [error, setError]       = useState('')

  // Load samples metadata once
  useEffect(() => {
    getSamples().then(s => setMaxSamples(s.num_test_samples)).catch(() => {})
  }, [setMaxSamples])

  // Keep input in sync when context changes externally
  useEffect(() => { setInputVal(String(sampleId)) }, [sampleId])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const id = parseInt(inputVal, 10)
    if (isNaN(id) || id < 0 || id >= maxSamples) {
      setError(`0 – ${maxSamples - 1}`)
      return
    }
    setError('')
    setSampleId(id)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <div style={{ color: '#3d5275', fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 2 }}>
        Sample ID
      </div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          type="number"
          value={inputVal}
          min={0}
          max={maxSamples - 1}
          onChange={e => { setInputVal(e.target.value); setError('') }}
          style={{
            width: 80, padding: '5px 8px',
            background: '#0a1425', border: '1px solid #1a2c4a',
            borderRadius: 5, color: '#e2e8f0', fontSize: '0.82rem',
            outline: 'none',
          }}
        />
        <button type="submit" title="Go" style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 28, height: 28,
          background: '#1d4ed8', border: 'none', borderRadius: 5,
          color: '#fff', cursor: 'pointer',
        }}>
          <Search size={13} />
        </button>
      </div>
      {error
        ? <div style={{ color: '#ef4444', fontSize: '0.65rem' }}>Valid range: {error}</div>
        : <div style={{ color: '#3d5275', fontSize: '0.65rem' }}>0 – {maxSamples - 1}</div>
      }
    </form>
  )
}
