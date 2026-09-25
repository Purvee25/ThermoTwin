import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from './api'
import { PatientList } from './components/PatientList'
import { ReviewScreen } from './components/ReviewScreen'
import { TwinView } from './components/TwinView'

const SHIFT_START_MINUTE = 20
const SHIFT_END_MINUTE = 379
const DEFAULT_MINUTE = 260

function minuteToClock(minute: number): string {
  const total = 11 * 60 + (minute - SHIFT_START_MINUTE)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

type View = 'twin' | 'review'

export default function App() {
  const [view, setView] = useState<View>('twin')
  const [minute, setMinute] = useState(DEFAULT_MINUTE)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const meta = useQuery({ queryKey: ['meta'], queryFn: api.meta })
  const patients = useQuery({
    queryKey: ['patients', minute],
    queryFn: () => api.patients(minute),
    placeholderData: (previous) => previous,
  })

  const activeId = selectedId ?? patients.data?.[0]?.patient_id ?? null
  const active = patients.data?.find((p) => p.patient_id === activeId) ?? null

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <h1>
            Thermo<span>Twin</span>
          </h1>
          <p>Hypertension digital twin · heat-crisis forecast for outdoor workers</p>
        </div>
        {meta.data && (
          <div className="day-chip">
            Replaying {meta.data.location}, {meta.data.date} · peak air{' '}
            <strong>{meta.data.max_air_temp_c.toFixed(1)} °C</strong>
          </div>
        )}
      </header>

      <nav className="tabs" aria-label="Views">
        <button type="button" aria-pressed={view === 'twin'} onClick={() => setView('twin')}>
          Live twin
        </button>
        <button type="button" aria-pressed={view === 'review'} onClick={() => setView('review')}>
          Pre-summer review
        </button>
      </nav>

      {view === 'review' ? (
        <ReviewScreen />
      ) : (
        <>
          <label className="replay">
            <span>Shift time</span>
            <input
              type="range"
              min={SHIFT_START_MINUTE + 15}
              max={SHIFT_END_MINUTE}
              value={minute}
              onChange={(e) => setMinute(Number(e.target.value))}
              aria-label="Replay time"
            />
            <span className="clock">{minuteToClock(minute)}</span>
          </label>

          {patients.isError && (
            <p className="panel notice error">
              Could not reach the ThermoTwin API. Start it with{' '}
              <code>uv run uvicorn thermotwin.api.main:app</code>.
            </p>
          )}

          <div className="layout">
            <section className="panel" aria-label="Patients">
              <h2 className="panel-title">Patients · highest risk now</h2>
              {patients.isPending ? (
                <p className="notice">Loading twins…</p>
              ) : (
                <PatientList
                  patients={patients.data ?? []}
                  activeId={activeId}
                  onSelect={setSelectedId}
                />
              )}
            </section>

            <section className="panel" aria-label="Patient twin">
              {active && meta.data ? (
                <TwinView patient={active} minute={minute} dangerCoreC={meta.data.danger_core_c} />
              ) : (
                <p className="notice">Select a patient.</p>
              )}
            </section>
          </div>
        </>
      )}

      {meta.data && <p className="footer">{meta.data.disclaimer}</p>}
    </div>
  )
}
