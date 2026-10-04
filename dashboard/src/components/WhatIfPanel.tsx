import { useState } from "react";
import type { Scenario, WhatIf } from "../api";

const DURATIONS = [10, 15, 20, 30, 45, 60];

interface Props {
  minute: number;
  clock: string;
  pending: boolean;
  error?: string;
  result?: WhatIf;
  onRun: (start: number, duration: number) => void;
  onReset: () => void;
}

export function WhatIfPanel({
  minute,
  clock,
  pending,
  error,
  result,
  onRun,
  onReset,
}: Props) {
  const [duration, setDuration] = useState(20);

  return (
    <div className="whatif">
      <div>
        <h3 style={{ margin: 0, fontSize: "0.95rem" }}>
          What if they rest in the shade?
        </h3>
        <p className="hint" style={{ margin: "2px 0 0" }}>
          Re-runs this worker's twin with an extra rest break starting at the
          selected shift time.
        </p>
      </div>
      <div className="whatif-controls">
        <label>
          Rest for
          <select
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
          >
            {DURATIONS.map((d) => (
              <option key={d} value={d}>
                {d} min
              </option>
            ))}
          </select>
        </label>
        <span>from {clock}</span>
        <button
          type="button"
          className="btn"
          disabled={pending}
          onClick={() => onRun(minute, duration)}
        >
          {pending ? "Simulating…" : "Simulate rest break"}
        </button>
        {result && (
          <button type="button" className="btn ghost" onClick={onReset}>
            Clear
          </button>
        )}
      </div>
      {error && <p className="error">What-if failed: {error}</p>}
      {result && (
        <Comparison baseline={result.baseline} scenario={result.scenario} />
      )}
    </div>
  );
}

function delta(before: number, after: number): "better" | "worse" | "same" {
  if (after < before) return "better";
  if (after > before) return "worse";
  return "same";
}

function Comparison({
  baseline,
  scenario,
}: {
  baseline: Scenario;
  scenario: Scenario;
}) {
  const items: [string, number, number, string, string][] = [
    [
      "Peak twin core",
      baseline.peak_twin_core_c,
      scenario.peak_twin_core_c,
      `${baseline.peak_twin_core_c.toFixed(2)} °C`,
      `${scenario.peak_twin_core_c.toFixed(2)} °C`,
    ],
    [
      "Alert minutes",
      baseline.alert_minutes,
      scenario.alert_minutes,
      String(baseline.alert_minutes),
      String(scenario.alert_minutes),
    ],
    [
      "Minutes truly ≥38 °C",
      baseline.true_danger_minutes,
      scenario.true_danger_minutes,
      String(baseline.true_danger_minutes),
      String(scenario.true_danger_minutes),
    ],
  ];
  const peakUnchanged = baseline.peak_twin_core_c === scenario.peak_twin_core_c;
  return (
    <div className="compare">
      {items.map(([label, before, after, beforeStr, afterStr]) => {
        const d = delta(before, after);
        return (
          <div key={label} className="stat">
            <div className="label">{label}</div>
            <div className="value">
              {beforeStr}{" "}
              <small className={`arrow-${d}`}>
                → {afterStr}
                {d === "better" ? " ↓" : d === "worse" ? " ↑" : ""}
              </small>
            </div>
          </div>
        );
      })}
      {peakUnchanged && (
        <p className="hint" style={{ gridColumn: "1 / -1", marginTop: 4 }}>
          Peak unchanged: by this point in the shift the thermal load is already
          committed. Try an earlier rest break for greater effect.
        </p>
      )}
    </div>
  );
}
