"""Fuse heart-rate-based ECTemp with skin temperature, fitted on real PROSPIE heat trials.

The fusion is a small linear model on top of the ECTemp estimate. It is fitted and
evaluated with leave-participants-out cross-validation so no person appears in both
training and test folds.

Run: uv run python -m thermotwin.fusion
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

from thermotwin.ectemp import estimate_core_temperature
from thermotwin.prospie import load_trials

FEATURES = ["ectemp_c", "skin_temp_c", "skin_rise_c"]
N_FOLDS = 5
RIDGE_ALPHA = 1.0
DANGER_CORE_C = 38.0
MODEL_PATH = Path("models/fusion.json")
REPORT_PATH = Path("reports/prospie_validation.csv")


@dataclass(frozen=True)
class FusionModel:
    """Linear fusion: core = intercept + sum(coef_i * feature_i)."""

    intercept: float
    coefficients: dict[str, float]

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        weights = np.array([self.coefficients[f] for f in FEATURES])
        return self.intercept + features[FEATURES].to_numpy() @ weights


def add_features(trials: pd.DataFrame) -> pd.DataFrame:
    """Per trial: run ECTemp over heart rate and track skin warming since the trial started."""
    out = trials.copy()
    out["ectemp_c"] = np.nan
    for _, idx in out.groupby("trial_id").groups.items():
        out.loc[idx, "ectemp_c"] = estimate_core_temperature(out.loc[idx, "heart_rate"])[0]
    out["skin_rise_c"] = out["skin_temp_c"] - out.groupby("trial_id")["skin_temp_c"].transform(
        "first"
    )
    return out


def fit(data: pd.DataFrame) -> FusionModel:
    reg = Ridge(alpha=RIDGE_ALPHA).fit(data[FEATURES], data["core_temp_c"])
    return FusionModel(
        float(reg.intercept_), dict(zip(FEATURES, map(float, reg.coef_), strict=True))
    )


def _metrics(truth: np.ndarray, estimate: np.ndarray) -> dict[str, float]:
    danger = truth >= DANGER_CORE_C
    return {
        "rmse_c": float(np.sqrt(np.mean((estimate - truth) ** 2))),
        "bias_c": float(np.mean(estimate - truth)),
        "danger_sensitivity": float((estimate[danger] >= DANGER_CORE_C).mean()),
        "false_alarm_rate": float((estimate[~danger] >= DANGER_CORE_C).mean()),
    }


def cross_validate(data: pd.DataFrame) -> pd.DataFrame:
    """Leave-participants-out comparison of ECTemp alone versus the fusion."""
    data = data.assign(fused_c=np.nan)
    for train, test in GroupKFold(n_splits=N_FOLDS).split(data, groups=data["participant"]):
        model = fit(data.iloc[train])
        data.iloc[test, data.columns.get_loc("fused_c")] = model.predict(data.iloc[test])
    truth = data["core_temp_c"].to_numpy()
    return pd.DataFrame(
        {
            "ECTemp (HR only)": _metrics(truth, data["ectemp_c"].to_numpy()),
            "Fusion (HR + skin)": _metrics(truth, data["fused_c"].to_numpy()),
        }
    ).T.round(3)


def main() -> None:
    data = add_features(load_trials())
    report = cross_validate(data)
    print(f"{data['participant'].nunique()} participants, {data['trial_id'].nunique()} trials")
    print(report.to_string())

    model = fit(data)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(asdict(model), indent=2))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(REPORT_PATH)
    print(f"model coefficients: {model}")


if __name__ == "__main__":
    main()
