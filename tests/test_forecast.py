import numpy as np

from thermotwin.cohort import generate_cohort
from thermotwin.forecast import FEATURES, physics_rise, run, shift_features
from thermotwin.weather import delhi_heatwave_2024


def test_physics_rise_increases_with_heat_and_work():
    rise = physics_rise(
        np.array([35.0, 45.0, 45.0]), np.array([30.0, 15.0, 15.0]), np.array([1.2, 1.2, 3.0])
    )

    assert rise[0] < rise[1] < rise[2]


def test_shift_features_have_no_missing_values_or_future_leak():
    day = delhi_heatwave_2024()[8]
    df = shift_features(generate_cohort(1, seed=2)[0], day, seed=2)

    assert not df[[*FEATURES, "label"]].isna().any().any()
    assert "true_core_c" not in FEATURES
    assert set(df["label"].unique()) <= {0.0, 1.0}


def test_forecast_beats_weather_only_alert():
    report = run(n_patients=40, seed=3)

    assert (
        report["ThermoTwin 60-min forecast"]["auroc"] > report["Weather-only heat alert"]["auroc"]
    )
