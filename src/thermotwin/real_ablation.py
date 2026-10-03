"""Beta-blocker ablation on real heat-trial data (PROSPIE).

Real heart rate and real rectal core temperature are used as-is. Only the drug effect
is synthetic: each trial's heart rate is blunted with a hidden, randomly drawn
beta-blocker response. The twin sees just the medication list and population priors.

NOTE: blunt() draws from the same distribution as the cohort's beta-blocker priors,
so the twin undoes a drug effect it was designed to correct — results are optimistic
by construction. Three seeds are used to assess result stability across random draws.

Run: uv run python -m thermotwin.real_ablation
"""

import numpy as np
import pandas as pd

from thermotwin import paths
from thermotwin.ectemp import estimate_core_temperature
from thermotwin.medication import RESTING_WINDOW_MIN, DrugClass, twin_core_temperature
from thermotwin.prospie import load_trials

DANGER_CORE_C = 38.0
ALERT_Z = 1.0
SEEDS = [42, 17, 99]  # three seeds for stability check
SEED = 42  # kept for backward compatibility
REPORT_PATH = paths.REPORTS_DIR / "real_ablation_summary.csv"
BETA_BLOCKER = frozenset({DrugClass.BETA_BLOCKER})


def blunt(heart_rate: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Apply a hidden beta-blocker response drawn from the same ranges as the cohort."""
    retained = float(np.clip(rng.normal(0.68, 0.07), 0.5, 0.9))
    resting_ratio = float(np.clip(rng.normal(0.87, 0.04), 0.78, 0.96))
    resting = float(np.median(heart_rate[:RESTING_WINDOW_MIN]))
    return resting * resting_ratio + (heart_rate - resting) * retained


def _score(truth: np.ndarray, est: np.ndarray, var: np.ndarray) -> dict[str, float]:
    danger = truth >= DANGER_CORE_C
    alert = est + ALERT_Z * np.sqrt(var) >= DANGER_CORE_C
    return {
        "sq_err": float(np.sum((est - truth) ** 2)),
        "err": float(np.sum(est - truth)),
        "n": truth.size,
        "danger": int(danger.sum()),
        "caught": int((danger & alert).sum()),
        "safe": int((~danger).sum()),
        "false_alarm": int((~danger & alert).sum()),
    }


def _run_single_seed(seed: int) -> pd.DataFrame:
    """Run ablation for a single seed; returns a summary DataFrame."""
    rng = np.random.default_rng(seed)
    rows = []
    for trial_id, trial in load_trials().groupby("trial_id"):
        truth = trial["core_temp_c"].to_numpy()
        blunted = blunt(trial["heart_rate"].to_numpy(), rng)
        for name, (est, var) in {
            "ECTemp (HR only)": estimate_core_temperature(blunted),
            "ThermoTwin (medication-aware)": twin_core_temperature(blunted, BETA_BLOCKER),
        }.items():
            rows.append({"trial_id": trial_id, "estimator": name, **_score(truth, est, var)})

    totals = pd.DataFrame(rows).groupby("estimator").sum(numeric_only=True)
    summary = pd.DataFrame(
        {
            "rmse_c": np.sqrt(totals["sq_err"] / totals["n"]),
            "bias_c": totals["err"] / totals["n"],
            "danger_sensitivity": totals["caught"] / totals["danger"],
            "false_alarm_rate": totals["false_alarm"] / totals["safe"],
        }
    ).round(3)
    summary["seed"] = seed
    return summary


def run() -> pd.DataFrame:
    """Run ablation with SEED=42 (single-seed; for backward compat).

    Use run_multi_seed() for stability across seeds.
    """
    return _run_single_seed(SEED)


def run_multi_seed(seeds: list[int] | None = None) -> pd.DataFrame:
    """Run ablation over multiple seeds and report mean ± range.

    Args:
        seeds: List of integer seeds. Defaults to SEEDS = [42, 17, 99].

    Returns:
        DataFrame with per-seed rows plus a summary row showing mean (range) for each metric.
    """
    if seeds is None:
        seeds = SEEDS

    per_seed = [_run_single_seed(s) for s in seeds]
    combined = pd.concat(per_seed).reset_index()  # estimator becomes a column

    # Save full per-seed CSV (with seed column)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(REPORT_PATH, index=False)

    # Build summary: mean and range per estimator/metric
    metric_cols = ["rmse_c", "bias_c", "danger_sensitivity", "false_alarm_rate"]
    agg = combined.groupby("estimator")[metric_cols]
    means = agg.mean().round(3)
    mins = agg.min()
    maxs = agg.max()
    ranges = (maxs - mins).round(3)

    summary_rows = []
    for est in means.index:
        for s_df in per_seed:
            row = s_df.loc[est].to_dict()
            row["estimator"] = est
            summary_rows.append(row)
        # Add mean±range row
        mean_row = {"estimator": est, "seed": "mean(range)"}
        for col in metric_cols:
            mean_row[col] = f"{means.loc[est, col]:.3f} ({ranges.loc[est, col]:.3f})"
        summary_rows.append(mean_row)

    return pd.DataFrame(summary_rows).set_index(["estimator", "seed"])


if __name__ == "__main__":
    result = run_multi_seed()
    print(result.to_string())
