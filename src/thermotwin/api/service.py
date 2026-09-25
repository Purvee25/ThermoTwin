"""Twin service: demo workers on a real Delhi heatwave day, forecasts and what-if runs."""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import norm

from thermotwin.api.schemas import (
    MedicationFlag,
    Meta,
    PatientSummary,
    RiskStatus,
    ScenarioSummary,
    Timeline,
    TimelinePoint,
)
from thermotwin.cohort import Patient, generate_cohort
from thermotwin.forecast import (
    ALERT_PROBABILITY,
    DANGER_CORE_C,
    MODEL_PATH,
    WARMUP_MIN,
    features_from_shift,
    learn_bias,
)
from thermotwin.medication import DrugClass
from thermotwin.personal import PersonalBias
from thermotwin.simulator import PRE_SHIFT_REST_MIN, simulate_shift
from thermotwin.weather import DayWeather, delhi_heatwave_2024

DEMO_PATIENTS = 12
DEMO_SEED = 2026
DEMO_DATE = "2024-05-28"
LEARNING_DATES = ("2024-05-25", "2024-05-31")
INTERVAL_Z = 1.2816  # two-sided 80% interval
VALIDATION_PATH = Path("reports/personal_validation.csv")
AMBER_PROBABILITY = 0.25
DISCLAIMER = "Research prototype on simulated patients and real weather. Not a medical device."

NAMES = (
    "Ramesh Kumar", "Suresh Yadav", "Anil Verma", "Imran Khan", "Vijay Singh", "Manoj Patel",
    "Lakshmi Devi", "Rahul Gupta", "Arjun Nair", "Deepak Sharma", "Sunita Rao", "Farhan Ali",
)  # fmt: skip
OCCUPATIONS = ("Delivery rider", "Construction worker", "Street vendor", "Farm labourer")
FLAG_NOTES = {
    DrugClass.BETA_BLOCKER: "Blunts heart-rate rise; twin corrects wearable readings",
    DrugClass.ACE_INHIBITOR: "Higher heat-illness risk in heatwaves (2026 cohort study)",
    DrugClass.ARB: "Higher heat-illness risk in heatwaves (2026 cohort study)",
    DrugClass.CALCIUM_CHANNEL_BLOCKER: "Higher heat-illness risk in heatwaves (2026 cohort study)",
    DrugClass.THIAZIDE_DIURETIC: "Watch hydration and kidney function; avoid NSAIDs",
    DrugClass.NSAID: "With a diuretic and ACE inhibitor/ARB: kidney-injury risk in heat",
}


class PatientNotFoundError(KeyError):
    pass


@dataclass
class DemoPatient:
    patient: Patient
    name: str
    occupation: str
    bias: PersonalBias
    seed: int
    timeline: pd.DataFrame


def load_empirical_rmse(path: Path = VALIDATION_PATH) -> dict[bool, float]:
    """Real-data (PROSPIE) RMSE of the twin with personal learning, keyed by beta-blocker use.

    The Kalman variance is over-confident, so the dashboard band uses measured error instead.
    """
    rows = {r["scenario"]: r for r in csv.DictReader(path.open())
            if r["estimator"] == "Twin + learned personal bias"}  # fmt: skip
    return {True: float(rows["beta-blocker"]["rmse_c"]), False: float(rows["no drug"]["rmse_c"])}


def _clock(hour: float) -> str:
    total = round(hour * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _status(probability: float) -> RiskStatus:
    if probability >= ALERT_PROBABILITY:
        return "red"
    return "amber" if probability >= AMBER_PROBABILITY else "green"


class TwinService:
    """Holds demo patients and the trained forecaster."""

    def __init__(self, model_path: Path = MODEL_PATH, n_patients: int = DEMO_PATIENTS) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"{model_path} missing; run "
                "`uv run python -m thermotwin.forecast --patients 200 --save-model`"
            )
        self._rmse = load_empirical_rmse()
        artifact = joblib.load(model_path)
        self._model, self._features = artifact["model"], artifact["features"]
        days = {d.date: d for d in delhi_heatwave_2024()}
        self.day: DayWeather = days[DEMO_DATE]
        learning_days = [days[d] for d in LEARNING_DATES]

        self._patients: dict[str, DemoPatient] = {}
        for i, patient in enumerate(generate_cohort(n_patients, seed=DEMO_SEED)):
            seed = DEMO_SEED + i
            bias = learn_bias(patient, learning_days, seed, np.random.default_rng(seed))
            self._patients[patient.patient_id] = DemoPatient(
                patient=patient,
                name=NAMES[i % len(NAMES)],
                occupation=OCCUPATIONS[i % len(OCCUPATIONS)],
                bias=bias,
                seed=seed,
                timeline=self._run(patient, bias, seed),
            )

    def _run(
        self, patient: Patient, bias: PersonalBias, seed: int, extra_rest: Sequence = ()
    ) -> pd.DataFrame:
        shift = simulate_shift(patient, self.day, seed=seed, extra_rest=extra_rest)
        df = features_from_shift(patient, self.day, shift, bias)
        risk = self._model.predict_proba(df[self._features])[:, 1]
        ready = df["minutes_into_shift"] >= WARMUP_MIN
        df["risk_60"] = np.where(ready, risk, np.nan)
        rmse = self._rmse[patient.on_beta_blocker]
        df["p_above_now"] = norm.sf(DANGER_CORE_C, loc=df["twin_core_c"], scale=rmse)
        return df

    def _get(self, patient_id: str) -> DemoPatient:
        try:
            return self._patients[patient_id]
        except KeyError as exc:
            raise PatientNotFoundError(patient_id) from exc

    def meta(self) -> Meta:
        return Meta(
            location="Delhi, India",
            date=self.day.date,
            max_air_temp_c=self.day.max_temp_c,
            danger_core_c=DANGER_CORE_C,
            alert_probability=ALERT_PROBABILITY,
            disclaimer=DISCLAIMER,
        )

    def summaries(self, minute: int | None = None) -> list[PatientSummary]:
        """All patients, highest risk first; `minute` sets the replay time for `risk_now`."""
        out = [self._summary(p, minute) for p in self._patients.values()]
        return sorted(
            out,
            key=lambda s: (max(s.risk_now or 0.0, s.p_above_now or 0.0), s.peak_risk),
            reverse=True,
        )

    def _summary(self, demo: DemoPatient, minute: int | None) -> PatientSummary:
        df = demo.timeline
        risk = df["risk_60"]
        now, above = None, None
        if minute is not None and 0 <= minute < len(df) and not np.isnan(risk.iloc[minute]):
            now = float(risk.iloc[minute])
            above = float(df["p_above_now"].iloc[minute])
        alerts = df[risk >= ALERT_PROBABILITY]
        meds = sorted(demo.patient.medications)
        return PatientSummary(
            patient_id=demo.patient.patient_id,
            name=demo.name,
            age=demo.patient.age,
            sex=demo.patient.sex,
            occupation=demo.occupation,
            medications=[m.value for m in meds],
            flags=[MedicationFlag(drug_class=m.value, note=FLAG_NOTES[m]) for m in meds],
            learned_bias_c=round(demo.bias.bias_c, 3),
            risk_now=now,
            p_above_now=above,
            peak_risk=float(np.nanmax(risk)),
            status=_status(max(now, above) if now is not None else float(np.nanmax(risk))),
            first_alert_clock=_clock(alerts["hour"].iloc[0]) if len(alerts) else None,
        )

    def timeline(self, patient_id: str) -> Timeline:
        demo = self._get(patient_id)
        return self._to_timeline(patient_id, demo.timeline)

    def _to_timeline(self, patient_id: str, df: pd.DataFrame) -> Timeline:
        half_width = INTERVAL_Z * self._rmse[bool(df["beta_blocker"].iloc[0])]
        band = np.full(len(df), half_width)
        points = [
            TimelinePoint(
                minute=int(row.minute),
                clock=_clock(row.hour),
                twin_core_c=round(row.twin_core_c, 3),
                band_low_c=round(row.twin_core_c - b, 3),
                band_high_c=round(row.twin_core_c + b, 3),
                true_core_c=round(row.true_core_c, 3),
                heart_rate=round(row.heart_rate, 1),
                air_temp_c=round(row.air_temp_c, 1),
                activity_par=round(row.par, 2),
                risk_60=None if np.isnan(row.risk_60) else round(row.risk_60, 3),
                p_above_now=round(row.p_above_now, 3),
                alert=bool(row.risk_60 >= ALERT_PROBABILITY),
            )
            for row, b in zip(df.itertuples(), band, strict=True)
        ]
        return Timeline(
            patient_id=patient_id, date=self.day.date, danger_core_c=DANGER_CORE_C, points=points
        )

    def what_if(
        self, patient_id: str, start_minute: int, duration_min: int
    ) -> tuple[ScenarioSummary, ScenarioSummary, Timeline]:
        """Re-run the shift with an extra rest break and compare with the baseline."""
        demo = self._get(patient_id)
        scenario = self._run(demo.patient, demo.bias, demo.seed, [(start_minute, duration_min)])
        return (
            _scenario_summary(demo.timeline),
            _scenario_summary(scenario),
            self._to_timeline(patient_id, scenario),
        )


def _scenario_summary(df: pd.DataFrame) -> ScenarioSummary:
    shift = df[df["minute"] >= PRE_SHIFT_REST_MIN]
    return ScenarioSummary(
        peak_twin_core_c=round(float(shift["twin_core_c"].max()), 3),
        alert_minutes=int((shift["risk_60"] >= ALERT_PROBABILITY).sum()),
        true_danger_minutes=int((shift["true_core_c"] >= DANGER_CORE_C).sum()),
    )
