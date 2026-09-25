import type { PatientSummary } from '../api'
import { drugLabel } from '../drugs'

function riskText(patient: PatientSummary): string {
  const risk =
    patient.risk_now === null
      ? patient.peak_risk
      : Math.max(patient.risk_now, patient.p_above_now ?? 0)
  return `${Math.round(risk * 100)}%`
}

interface Props {
  patients: PatientSummary[]
  activeId: string | null
  onSelect: (id: string) => void
}

export function PatientList({ patients, activeId, onSelect }: Props) {
  return (
    <ul className="patient-list">
      {patients.map((p) => (
        <li key={p.patient_id}>
          <button
            type="button"
            className="patient-card"
            aria-current={p.patient_id === activeId}
            onClick={() => onSelect(p.patient_id)}
          >
            <span className={`dot ${p.status}`} aria-label={`${p.status} risk`} />
            <span className="patient-name">{p.name}</span>
            <span className={`risk-pill ${p.status}`} title="Higher of: chance core is ≥ 38 °C now, and forecast chance within 60 min">
              {riskText(p)}
            </span>
            <span className="patient-sub">
              {p.age}
              {p.sex === 'female' ? 'F' : 'M'} · {p.occupation}
              {p.first_alert_clock ? ` · first alert ${p.first_alert_clock}` : ''}
            </span>
            <span className="chips">
              {p.medications.map((m) => (
                <span key={m} className={`chip${m === 'beta_blocker' ? ' bb' : ''}`}>
                  {drugLabel(m)}
                </span>
              ))}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
