"""60-minute heat-strain forecast: will core temperature reach 38 °C within the next hour?

Features use only what the twin can observe: its medication-aware core estimate and
uncertainty, heart-rate trends, current and forecast weather, activity, and EHR fields.
Shifts replay real Delhi heatwave days (May-June 2024). Patients are split so nobody
appears in both training and test.

Run: uv run python -m thermotwin.forecast --patients 200
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pythermalcomfort.models import two_nodes_gagge
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from thermotwin.cohort import Patient, generate_cohort
from thermotwin.medication import twin_core_temperature
from thermotwin.simulator import PRE_SHIFT_REST_MIN, SUN_RADIANT_OFFSET_C, simulate_shift
from thermotwin.weather import DayWeather, delhi_heatwave_2024

DANGER_CORE_C = 38.0
HORIZON_MIN = 60
TREND_MIN = 15
WARMUP_MIN = 15
TEST_SHARE = 0.3
ALERT_PROBABILITY = 0.5
MIN_LEAD_MIN = 30
REPORT_PATH = Path("reports/forecast_summary.json")
ASSUMED_CLOTHING_CLO = 0.75
FORECAST_WIND_M_S = 1.5
GAGGE_NEUTRAL_CORE_C = 36.8

FEATURES = [
    "twin_core_c",
    "twin_core_sd",
    "twin_core_slope",
    "heart_rate",
    "hr_slope",
    "air_temp_c",
    "air_temp_in_60",
    "rh",
    "par_recent",
    "minutes_into_shift",
    "physics_rise_60",
    "physics_projection_c",
    "beta_blocker",
    "age",
    "bmi",
]


def shift_features(patient: Patient, day: DayWeather, seed: int) -> pd.DataFrame:
    """One simulated shift turned into per-minute features and the 60-minute label."""
    shift = simulate_shift(patient, day, seed=seed)
    est, var = twin_core_temperature(shift["heart_rate"].to_numpy(), patient.medications)
    core = shift["core_temp_c"]
    future_max = core[::-1].rolling(HORIZON_MIN, min_periods=HORIZON_MIN).max()[::-1].shift(-1)

    df = pd.DataFrame(
        {
            "patient_id": patient.patient_id,
            "date": day.date,
            "minute": shift["minute"],
            "true_core_c": core,
            "twin_core_c": est,
            "twin_core_sd": np.sqrt(var),
            "heart_rate": shift["heart_rate"],
            "air_temp_c": shift["air_temp_c"],
            "air_temp_in_60": shift["air_temp_c"].shift(-HORIZON_MIN),
            "rh": shift["rh"],
            "par_recent": shift["par"].rolling(TREND_MIN, min_periods=1).mean(),
            "minutes_into_shift": shift["minute"] - PRE_SHIFT_REST_MIN,
            "beta_blocker": int(patient.on_beta_blocker),
            "age": patient.age,
            "bmi": patient.weight_kg / patient.height_m**2,
            "label": (future_max >= DANGER_CORE_C).astype(float).where(future_max.notna()),
        }
    )
    air_next = shift["air_temp_c"][::-1].rolling(HORIZON_MIN, min_periods=1).mean()[::-1]
    df["physics_rise_60"] = physics_rise(
        air_next.to_numpy(), df["rh"].to_numpy(), df["par_recent"].to_numpy()
    )
    df["physics_projection_c"] = df["twin_core_c"] + df["physics_rise_60"]
    df["twin_core_slope"] = df["twin_core_c"].diff(TREND_MIN) / TREND_MIN
    df["hr_slope"] = df["heart_rate"].diff(TREND_MIN) / TREND_MIN
    keep = df["minutes_into_shift"] >= WARMUP_MIN
    return df[keep].dropna(subset=[*FEATURES, "label"])


def physics_rise(air_c: np.ndarray, rh: np.ndarray, par: np.ndarray) -> np.ndarray:
    """Core-temperature rise the Gagge two-node model predicts for one hour of exposure.

    The twin uses Gagge (not the JOS-3 ground truth) with population-average clothing,
    so this projection is an honest, imperfect forward model.
    """
    result = two_nodes_gagge(
        tdb=air_c,
        tr=air_c + SUN_RADIANT_OFFSET_C,
        v=FORECAST_WIND_M_S,
        rh=rh,
        met=par,
        clo=ASSUMED_CLOTHING_CLO,
        round_output=False,
    )
    return np.asarray(result.t_core) - GAGGE_NEUTRAL_CORE_C


def build_dataset(n_patients: int, seed: int) -> pd.DataFrame:
    days = delhi_heatwave_2024()
    rng = np.random.default_rng(seed)
    frames = [
        shift_features(p, days[int(rng.integers(len(days)))], seed=seed + i)
        for i, p in enumerate(generate_cohort(n_patients, seed=seed))
    ]
    return pd.concat(frames, ignore_index=True)


def nowcast_probability(df: pd.DataFrame) -> np.ndarray:
    """Baseline without ML: chance the current twin estimate is already above the threshold."""
    return norm.cdf((df["twin_core_c"] - DANGER_CORE_C) / df["twin_core_sd"])


def lead_times(df: pd.DataFrame, prob: np.ndarray) -> list[float]:
    """Minutes between first alert and each shift's first danger minute (NaN if unwarned)."""
    df = df.assign(prob=prob)
    leads = []
    for _, shift in df.groupby(["patient_id", "date"]):
        danger = shift["true_core_c"] >= DANGER_CORE_C
        if not danger.any():
            continue
        onset = shift.loc[danger.idxmax(), "minute"]
        alerts = shift[(shift["prob"] >= ALERT_PROBABILITY) & (shift["minute"] <= onset)]
        leads.append(float(onset - alerts["minute"].min()) if len(alerts) else np.nan)
    return leads


def evaluate(df: pd.DataFrame, prob: np.ndarray) -> dict[str, float]:
    y = df["label"].to_numpy()
    leads = np.array(lead_times(df, prob))
    warned = leads[~np.isnan(leads)]
    return {
        "auroc": round(float(roc_auc_score(y, prob)), 3),
        "auprc": round(float(average_precision_score(y, prob)), 3),
        "brier": round(float(brier_score_loss(y, prob)), 3),
        "episodes": int(leads.size),
        f"warned_{MIN_LEAD_MIN}min_ahead_pct": round(
            100 * float(np.mean(np.nan_to_num(leads, nan=-1) >= MIN_LEAD_MIN)), 1
        ),
        "median_lead_min": float(np.median(warned)) if warned.size else float("nan"),
        "alert_minutes_pct": round(100 * float(np.mean(prob >= ALERT_PROBABILITY)), 1),
    }


def split_by_patient(df: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = df["patient_id"].unique()
    rng = np.random.default_rng(seed)
    test_ids = set(rng.choice(ids, size=int(len(ids) * TEST_SHARE), replace=False))
    is_test = df["patient_id"].isin(test_ids)
    return df[~is_test], df[is_test]


def run(n_patients: int, seed: int) -> dict[str, dict[str, float]]:
    """Train on some patients, test on the rest; return metrics per method and subgroup."""
    train, test = split_by_patient(build_dataset(n_patients, seed), seed)

    weather_only = LogisticRegression(max_iter=1000).fit(
        train[["air_temp_c", "air_temp_in_60", "rh"]], train["label"]
    )
    twin = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=seed)
    twin.fit(train[FEATURES], train["label"])
    oracle_cols = [*FEATURES, "true_core_c"]
    oracle = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=seed)
    oracle.fit(train[oracle_cols], train["label"])

    probs = {
        "Weather-only heat alert": weather_only.predict_proba(
            test[["air_temp_c", "air_temp_in_60", "rh"]]
        )[:, 1],
        "Twin nowcast (no ML)": nowcast_probability(test),
        "Physics projection (no ML)": norm.cdf(
            (test["physics_projection_c"] - DANGER_CORE_C) / test["twin_core_sd"]
        ),
        "ThermoTwin 60-min forecast": twin.predict_proba(test[FEATURES])[:, 1],
        "Oracle ceiling (knows true current core)": oracle.predict_proba(test[oracle_cols])[:, 1],
    }
    report: dict[str, dict[str, float]] = {}
    for name, prob in probs.items():
        report[name] = evaluate(test, prob)
        for flag, group in ((1, "beta-blocker"), (0, "no beta-blocker")):
            mask = (test["beta_blocker"] == flag).to_numpy()
            report[f"{name} [{group}]"] = evaluate(test[mask], prob[mask])
    report["_meta"] = {
        "train_patients": int(train["patient_id"].nunique()),
        "test_patients": int(test["patient_id"].nunique()),
        "test_positive_rate": round(float(test["label"].mean()), 3),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--patients", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = run(args.patients, args.seed)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(pd.DataFrame(report).T.to_string())


if __name__ == "__main__":
    main()
