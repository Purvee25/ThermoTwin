import { useState } from 'react'
import type { Scenario, WhatIf } from '../api'

const DURATIONS = [10, 15, 20, 30, 45, 60]

interface Props {
  minute: number
  clock: string
  pending: boolean
  error?: string
  result?: WhatIf
  onRun: (start: number, duration: number) => void
  onReset: () => void
}

export function WhatIfPanel({ minute, clock, pending, error, result, onRun, onReset }: Props) {
  const [duration, setDuration] = useState(20)

  return (
    <div className="whatif">
      <div>
        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>What if they rest in the shade?</h3>
        <p className="hint" style={{ margin: '2px 0 0' }}>
          Re-runs this worker's twin with an extra rest break starting at the selected shift time.
        </p>
      </div>
      <div className="whatif-controls">
        <label>
          Rest for
          <select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {d} min
              </option>
            ))}
          </select>
        </label>
        <span>from {clock}</span>
        <button type="button" className="btn" disabled={pending} onClick={() => onRun(minute, duration)}>
          {pending ? 'Simulating…' : 'Simulate rest break'}
        </button>
        {result && (
          <button type="button" className="btn ghost" onClick={onReset}>
            Clear
          </button>
        )}
      </div>
      {error && <p className="error">What-if failed: {error}</p>}
      {result && <Comparison baseline={result.baseline} scenario={result.scenario} />}
    </div>
  )
}

function Comparison({ baseline, scenario }: { baseline: Scenario; scenario: Scenario }) {
  const items = [
    ['Peak twin core', `${baseline.peak_twin_core_c.toFixed(2)} °C`, `${scenario.peak_twin_core_c.toFixed(2)} °C`],
    ['Alert minutes', String(baseline.alert_minutes), String(scenario.alert_minutes)],
    ['Minutes truly ≥38 °C', String(baseline.true_danger_minutes), String(scenario.true_danger_minutes)],
  ] as const
  return (
    <div className="compare">
      {items.map(([label, before, after]) => (
        <div key={label} className="stat">
          <div className="label">{label}</div>
          <div className="value">
            {before} <small>→ {after}</small>
          </div>
        </div>
      ))}
    </div>
  )
}
