"""Signature ablation: does reading the medication record fix core-temperature estimates?

Compares plain ECTemp against the medication-aware twin on a simulated cohort and
writes a per-patient table, a group summary and a chart to the reports directory.

Run: uv run python -m thermotwin.ablation --patients 60
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from thermotwin.cohort import Patient, generate_cohort
from thermotwin.ectemp import estimate_core_temperature
from thermotwin.medication import twin_core_temperature
from thermotwin.simulator import PRE_SHIFT_REST_MIN, simulate_shift

DANGER_CORE_C = 38.0
REPORTS_DIR = Path("reports")


@dataclass(frozen=True)
class EstimateMetrics:
    rmse: float
    bias: float
    danger_minutes: int
    missed_danger_minutes: int


def score(true_core: np.ndarray, estimate: np.ndarray) -> EstimateMetrics:
    """Error metrics for one shift, excluding the pre-shift rest period."""
    truth, est = true_core[PRE_SHIFT_REST_MIN:], estimate[PRE_SHIFT_REST_MIN:]
    danger = truth >= DANGER_CORE_C
    return EstimateMetrics(
        rmse=float(np.sqrt(np.mean((est - truth) ** 2))),
        bias=float(np.mean(est - truth)),
        danger_minutes=int(danger.sum()),
        missed_danger_minutes=int((danger & (est < DANGER_CORE_C)).sum()),
    )


def evaluate_patient(patient: Patient, seed: int) -> list[dict]:
    shift = simulate_shift(patient, seed=seed)
    truth = shift["core_temp_c"].to_numpy()
    hr = shift["heart_rate"].to_numpy()
    estimators = {
        "ECTemp (HR only)": estimate_core_temperature(hr)[0],
        "ThermoTwin (medication-aware)": twin_core_temperature(hr, patient.medications)[0],
    }
    return [
        {
            "patient_id": patient.patient_id,
            "beta_blocker": patient.on_beta_blocker,
            "estimator": name,
            **vars(score(truth, estimate)),
        }
        for name, estimate in estimators.items()
    ]


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    grouped = results.groupby(["beta_blocker", "estimator"])
    summary = grouped.agg(
        patients=("patient_id", "nunique"),
        rmse_c=("rmse", "mean"),
        bias_c=("bias", "mean"),
        danger_minutes=("danger_minutes", "sum"),
        missed_danger_minutes=("missed_danger_minutes", "sum"),
    )
    summary["missed_danger_pct"] = (
        100 * summary["missed_danger_minutes"] / summary["danger_minutes"].replace(0, np.nan)
    )
    return summary.round(3)


def plot(summary: pd.DataFrame, path: Path) -> None:
    table = summary.reset_index()
    groups = {False: "No beta-blocker", True: "On beta-blocker"}
    estimators = list(table["estimator"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, metric, label in (
        (axes[0], "rmse_c", "Core temperature RMSE (°C)"),
        (axes[1], "missed_danger_pct", f"Danger minutes missed (≥{DANGER_CORE_C}°C), %"),
    ):
        width = 0.38
        x = np.arange(len(groups))
        for offset, estimator in enumerate(estimators):
            rows = table[table["estimator"] == estimator].set_index("beta_blocker")
            values = [rows.loc[g, metric] for g in groups]
            ax.bar(x + (offset - 0.5) * width, values, width, label=estimator)
        ax.set_xticks(x, list(groups.values()))
        ax.set_ylabel(label)
    axes[0].legend(fontsize=8)
    fig.suptitle("Reading the medication record fixes core-temperature estimates")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run(n_patients: int, seed: int, out_dir: Path = REPORTS_DIR) -> pd.DataFrame:
    """Run the ablation and write results; returns the group summary."""
    cohort = generate_cohort(n_patients, seed=seed)
    rows = [row for i, p in enumerate(cohort) for row in evaluate_patient(p, seed=seed + i)]
    results = pd.DataFrame(rows)
    summary = summarise(results)

    out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_dir / "ablation_per_patient.csv", index=False)
    summary.to_csv(out_dir / "ablation_summary.csv")
    plot(summary, out_dir / "ablation_beta_blocker.png")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--patients", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(run(args.patients, args.seed).to_string())


if __name__ == "__main__":
    main()
