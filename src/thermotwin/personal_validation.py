"""Validate cross-shift per-person bias learning on real PROSPIE trials.

For each trial, the twin learns the participant's bias only from their *other* trials,
using noisy simulated thermometer readings (±0.3 °C) at a few minutes. It then
corrects the held-out trial, which uses no reference reading at all. Scored after the
first 30 minutes, with and without a simulated beta-blocker effect on heart rate.

Run: uv run python -m thermotwin.personal_validation
"""

from pathlib import Path

import numpy as np
import pandas as pd

from thermotwin.ectemp import estimate_core_temperature
from thermotwin.medication import DrugClass, twin_core_temperature
from thermotwin.personal import PersonalBias, simulated_readings
from thermotwin.prospie import load_trials
from thermotwin.real_ablation import blunt

EVAL_FROM_MIN = 30
DANGER_CORE_C = 38.0
ALERT_Z = 1.0
SEED = 42
REPORT_PATH = Path("reports/personal_validation.csv")
BETA_BLOCKER = frozenset({DrugClass.BETA_BLOCKER})


def _score(truth: np.ndarray, est: np.ndarray, sd: np.ndarray) -> dict[str, float]:
    truth, est, sd = truth[EVAL_FROM_MIN:], est[EVAL_FROM_MIN:], sd[EVAL_FROM_MIN:]
    danger = truth >= DANGER_CORE_C
    alert = est + ALERT_Z * sd >= DANGER_CORE_C
    return {
        "sq_err": float(np.sum((est - truth) ** 2)),
        "err": float(np.sum(est - truth)),
        "n": truth.size,
        "danger": int(danger.sum()),
        "caught": int((danger & alert).sum()),
        "safe": int((~danger).sum()),
        "false_alarm": int((~danger & alert).sum()),
    }


def _estimate(trial: pd.DataFrame, beta_blocked: bool, rng: np.random.Generator):
    hr = trial["heart_rate"].to_numpy()
    if beta_blocked:
        return twin_core_temperature(blunt(hr, rng), BETA_BLOCKER)
    return estimate_core_temperature(hr)


def run() -> pd.DataFrame:
    trials = load_trials()
    rng = np.random.default_rng(SEED)
    rows = []
    for scenario, beta_blocked in (("no drug", False), ("beta-blocker", True)):
        shifts = {}
        for trial_id, trial in trials.groupby("trial_id"):
            est, var = _estimate(trial, beta_blocked, rng)
            core = trial["core_temp_c"].to_numpy()
            shifts[trial_id] = (trial["participant"].iloc[0], core, est, np.sqrt(var))

        for trial_id, (participant, core, est, sd) in shifts.items():
            bias = PersonalBias()
            for other_id, (other_p, other_core, other_est, _) in shifts.items():
                if other_p == participant and other_id != trial_id:
                    bias.add_shift(other_est, simulated_readings(other_core, rng))
            for name, estimate in (
                ("Twin (population)", est),
                ("Twin + learned personal bias", bias.correct(est)),
            ):
                rows.append({"scenario": scenario, "estimator": name, **_score(core, estimate, sd)})

    totals = pd.DataFrame(rows).groupby(["scenario", "estimator"]).sum(numeric_only=True)
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
