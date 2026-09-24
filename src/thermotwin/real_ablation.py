"""Beta-blocker ablation on real heat-trial data (PROSPIE).

Real heart rate and real rectal core temperature are used as-is. Only the drug effect
is synthetic: each trial's heart rate is blunted with a hidden, randomly drawn
beta-blocker response. The twin sees just the medication list and population priors.

Run: uv run python -m thermotwin.real_ablation
"""

from pathlib import Path

import numpy as np
import pandas as pd

from thermotwin.ectemp import estimate_core_temperature
from thermotwin.medication import RESTING_WINDOW_MIN, DrugClass, twin_core_temperature
from thermotwin.prospie import load_trials

DANGER_CORE_C = 38.0
ALERT_Z = 1.0
SEED = 42
REPORT_PATH = Path("reports/real_ablation_summary.csv")
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


def run() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
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
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(REPORT_PATH)
    return summary


if __name__ == "__main__":
    print(run().to_string())
