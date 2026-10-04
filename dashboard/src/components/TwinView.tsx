import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
} from "recharts";
import { api, type PatientSummary, type Point, type WhatIf } from "../api";
import { drugLabel } from "../drugs";
import { WhatIfPanel } from "./WhatIfPanel";

const ALERT_PERCENT = 50;

const X_TICK_EVERY = 60;

interface Row extends Point {
  band: [number, number];
  risk_pct: number | null;
  scenario_core?: number;
  scenario_risk_pct?: number | null;
}

function mergeRows(points: Point[], scenario: Point[] | undefined): Row[] {
  return points.map((p, i) => ({
    ...p,
    band: [p.band_low_c, p.band_high_c],
    risk_pct: p.risk_60 === null ? null : p.risk_60 * 100,
    scenario_core: scenario?.[i]?.twin_core_c,
    scenario_risk_pct:
      scenario?.[i]?.risk_60 == null
        ? undefined
        : (scenario[i].risk_60 as number) * 100,
  }));
}

interface Props {
  patient: PatientSummary;
  minute: number;
  dangerCoreC: number;
}

export function TwinView({ patient, minute, dangerCoreC }: Props) {
  const [showTruth, setShowTruth] = useState(false);
  const danger = useMemo(
    () =>
      getComputedStyle(document.documentElement)
        .getPropertyValue("--danger")
        .trim(),
    [],
  );
  const accent = useMemo(
    () =>
      getComputedStyle(document.documentElement)
        .getPropertyValue("--accent")
        .trim(),
    [],
  );
  const timeline = useQuery({
    queryKey: ["timeline", patient.patient_id],
    queryFn: () => api.timeline(patient.patient_id),
  });
  const whatIf = useMutation<
    WhatIf,
    Error,
    { start: number; duration: number }
  >({
    mutationKey: ["whatif", patient.patient_id],
    mutationFn: ({ start, duration }) =>
      api.whatIf(patient.patient_id, start, duration),
  });
  const scenario =
    whatIf.data?.timeline.patient_id === patient.patient_id
      ? whatIf.data
      : undefined;
  const explain = useQuery({
    queryKey: ["explain", patient.patient_id, minute],
    queryFn: () => api.explain(patient.patient_id, minute),
    enabled: minute > 0,
  });

  const rows = useMemo(
    () =>
      timeline.data
        ? mergeRows(timeline.data.points, scenario?.timeline.points)
        : [],
    [timeline.data, scenario],
  );
  const now = rows.find((r) => r.minute === minute);
  const ticks = rows
    .filter((r) => r.minute % X_TICK_EVERY === 20)
    .map((r) => r.clock);

  if (timeline.isPending) return <p className="notice">Loading twin…</p>;
  if (timeline.isError || !now)
    return <p className="notice error">Could not load this twin.</p>;

  const riskNow = now.risk_pct;
  return (
    <div className="twin">
      <div className="twin-head">
        <div>
          <h2>{patient.name}</h2>
          <p>
            {patient.age} · {patient.occupation} · learned personal bias{" "}
            {patient.learned_bias_c >= 0 ? "+" : ""}
            {patient.learned_bias_c.toFixed(2)} °C
          </p>
        </div>
        <div className="stats">
          <Stat
            label={`Core · ${now.clock}`}
            value={`${now.twin_core_c.toFixed(2)} °C`}
            danger={now.twin_core_c >= dangerCoreC}
          />
          <Stat
            label="Danger now"
            value={`${Math.round(now.p_above_now * 100)}%`}
            danger={now.p_above_now * 100 >= ALERT_PERCENT}
          />
          <Stat
            label="Risk in 60 min"
            value={riskNow === null ? "—" : `${Math.round(riskNow)}%`}
            danger={riskNow !== null && riskNow >= ALERT_PERCENT}
          />
          <Stat label="HR" value={`${Math.round(now.heart_rate)} bpm`} />
          <Stat label="Air" value={`${now.air_temp_c.toFixed(1)} °C`} />
        </div>
      </div>

      <div className="chart-card">
        <h3>
          Core temperature
          {scenario && (
            <span className="hint-inline"> · green = with rest break</span>
          )}
        </h3>
        <p className="hint">
          Shaded band = 80% confidence interval (sized from real heat-trial error on PROSPIE).
          Dashed red line = 38 °C danger threshold.
        </p>
        <ResponsiveContainer width="100%" height={260}>
          <ComposedChart
            data={rows}
            margin={{ top: 8, right: 12, bottom: 0, left: -12 }}
          >
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="clock"
              ticks={ticks}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <YAxis
              domain={[36.6, 39]}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
              tickFormatter={(v: number) => v.toFixed(1)}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
              }}
              itemStyle={{ color: "var(--text)" }}
              formatter={(value) =>
                Array.isArray(value)
                  ? value.map((v) => Number(v).toFixed(2)).join(" – ")
                  : Number(value).toFixed(2)
              }
            />
            <Area
              dataKey="band"
              stroke="none"
              fill="var(--band)"
              isAnimationActive={false}
              name="80% interval"
            />
            <Line
              dataKey="twin_core_c"
              stroke="var(--estimate)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="Twin estimate"
            />
            {showTruth && (
              <Line
                dataKey="true_core_c"
                stroke="var(--truth)"
                strokeDasharray="2 3"
                dot={false}
                isAnimationActive={false}
                name="Simulated truth"
              />
            )}
            {scenario && (
              <Line
                dataKey="scenario_core"
                stroke="var(--scenario)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="With rest break"
              />
            )}
            <ReferenceLine
              y={dangerCoreC}
              stroke={danger}
              strokeDasharray="6 4"
            />
            <ReferenceLine x={now.clock} stroke={accent} />
          </ComposedChart>
        </ResponsiveContainer>
        <label className="toggle">
          <input
            type="checkbox"
            checked={showTruth}
            onChange={(e) => setShowTruth(e.target.checked)}
          />
          Show simulated true core (validation only)
        </label>
      </div>

      <div className="chart-card">
        <h3>60-min risk forecast</h3>
        <ResponsiveContainer width="100%" height={150}>
          <ComposedChart
            data={rows}
            margin={{ top: 8, right: 12, bottom: 0, left: -12 }}
          >
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="clock"
              ticks={ticks}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "var(--muted)", fontSize: 12 }}
              unit="%"
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
              }}
              itemStyle={{ color: "var(--text)" }}
              formatter={(value) => `${Math.round(Number(value))}%`}
            />
            <Area
              dataKey="risk_pct"
              stroke="var(--danger)"
              fill="var(--red-soft)"
              isAnimationActive={false}
              name="Risk"
              connectNulls={false}
            />
            {scenario && (
              <Line
                dataKey="scenario_risk_pct"
                stroke="var(--scenario)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="With rest break"
              />
            )}
            <ReferenceLine
              y={ALERT_PERCENT}
              stroke={danger}
              strokeDasharray="6 4"
            />
            <ReferenceLine x={now.clock} stroke={accent} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <WhatIfPanel
        minute={minute}
        clock={now.clock}
        pending={whatIf.isPending}
        error={whatIf.error?.message}
        result={scenario}
        onRun={(start, duration) => whatIf.mutate({ start, duration })}
        onReset={() => whatIf.reset()}
      />

      {minute === 0 && (
        <div className="chart-card shap-placeholder">
          <h3>Why is this patient at risk?</h3>
          <p className="hint">Move the shift-time slider to a later time to see SHAP feature attribution for the 60-min forecast.</p>
        </div>
      )}
      {minute > 0 && !explain.data && !explain.isError && (
        <div className="chart-card shap-placeholder">
          <h3>Why is this patient at risk?</h3>
          <div className="skeleton-bar" /><div className="skeleton-bar" /><div className="skeleton-bar" />
        </div>
      )}
      {explain.data && explain.data.top_features.length > 0 && (
        <div className="chart-card">
          <h3>Why is this patient at risk?</h3>
          <p className="hint" style={{ marginBottom: 12 }}>
            Top factors driving the 60-min forecast · SHAP attribution
          </p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart
              data={explain.data.top_features.map((f) => ({
                name: f.feature.replace(/_/g, " "),
                pct: Math.abs(f.contribution_pct),
                positive: f.contribution > 0,
              }))}
              layout="vertical"
              margin={{ top: 0, right: 40, bottom: 0, left: 90 }}
            >
              <CartesianGrid stroke="var(--border)" horizontal={false} />
              <XAxis
                type="number"
                unit="%"
                tick={{ fill: "var(--muted)", fontSize: 11 }}
                domain={[0, "auto"]}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: "var(--text)", fontSize: 11 }}
                width={88}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                }}
                formatter={(v) => [`${Number(v).toFixed(1)}%`, "contribution"]}
              />
              <Bar
                dataKey="pct"
                radius={[0, 3, 3, 0]}
                isAnimationActive={false}
              >
                {explain.data.top_features.map((f, i) => (
                  <Cell
                    key={i}
                    fill={
                      f.contribution > 0 ? "var(--danger)" : "var(--accent)"
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="hint" style={{ marginTop: 6 }}>
            Red = raises risk · Blue = lowers risk
          </p>
        </div>
      )}

      <div className="chart-card">
        <h3>Medication heat-risk notes</h3>
        <ul className="flags">
          {patient.flags.map((f) => (
            <li key={f.drug_class}>
              <strong>{drugLabel(f.drug_class)}</strong>
              <span>{f.note}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className={`value${danger ? " danger" : ""}`}>{value}</div>
    </div>
  );
}
