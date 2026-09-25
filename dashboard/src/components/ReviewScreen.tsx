import { useQuery } from '@tanstack/react-query'
import { api, type ReviewItem } from '../api'
import { drugLabel } from '../drugs'

const PRIORITY_LABEL: Record<ReviewItem['priority'], string> = {
  high: 'High priority',
  medium: 'Medium',
  low: 'Low',
}

export function ReviewScreen() {
  const review = useQuery({ queryKey: ['review'], queryFn: api.review })

  if (review.isPending) return <p className="panel notice">Preparing review…</p>
  if (review.isError) return <p className="panel notice error">Could not load the review.</p>

  const counts = review.data.reduce(
    (acc, item) => ({ ...acc, [item.priority]: acc[item.priority] + 1 }),
    { high: 0, medium: 0, low: 0 },
  )

  return (
    <section className="panel review" aria-label="Pre-summer medication review">
      <div className="review-head">
        <div>
          <h2>Pre-summer medication &amp; heat review</h2>
          <p className="hint">
            Suggestions for clinician review before the heat season. They combine medication and kidney
            records with each twin's replay of the 28 May 2024 Delhi heatwave. Priority is a triage
            heuristic, not a validated clinical score.
          </p>
        </div>
        <div className="review-actions">
          <span className="chip">{counts.high} high</span>
          <span className="chip">{counts.medium} medium</span>
          <span className="chip">{counts.low} low</span>
          <button type="button" className="btn ghost" onClick={() => window.print()}>
            Print list
          </button>
        </div>
      </div>

      <ol className="review-list">
        {review.data.map((item) => (
          <ReviewRow key={item.patient_id} item={item} />
        ))}
      </ol>
    </section>
  )
}

function ReviewRow({ item }: { item: ReviewItem }) {
  const egfrChange = ((item.egfr_now - item.egfr_last_year) / item.egfr_last_year) * 100
  const kidneyConcern = item.findings.some((f) => f.code === 'kidney_decline')
  return (
    <li className="review-row">
      <div className="review-patient">
        <span className={`priority ${item.priority}`}>{PRIORITY_LABEL[item.priority]}</span>
        <strong>{item.name}</strong>
        <span className="hint">
          {item.age} · {item.occupation}
        </span>
        <span className="chips">
          {item.medications.map((m) => (
            <span key={m} className={`chip${m === 'beta_blocker' ? ' bb' : ''}`}>
              {drugLabel(m)}
            </span>
          ))}
        </span>
        <dl className="review-facts">
          <div>
            <dt>eGFR</dt>
            <dd>
              {item.egfr_last_year.toFixed(0)} → {item.egfr_now.toFixed(0)}{' '}
              <span className={kidneyConcern ? 'danger-text' : ''}>
                ({egfrChange >= 0 ? '+' : ''}
                {egfrChange.toFixed(0)}%)
              </span>
            </dd>
          </div>
          <div>
            <dt>Heat strain (replay)</dt>
            <dd>{item.heat_minutes} min ≥ 38 °C</dd>
          </div>
        </dl>
      </div>
      {item.findings.length === 0 ? (
        <p className="hint">No heat-related medication concerns found.</p>
      ) : (
        <ul className="findings">
          {item.findings.map((f) => (
            <li key={f.code}>
              <div className="finding-title">{f.title}</div>
              <div>{f.detail}</div>
              <div className="finding-action">→ {f.action}</div>
              <div className="finding-evidence">{f.evidence}</div>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}
