import numpy as np
import pytest

from thermotwin.prospie import RAW_PATH
from thermotwin.real_ablation import blunt

needs_prospie = pytest.mark.skipif(not RAW_PATH.exists(), reason="PROSPIE data not downloaded")


def test_blunt_lowers_heart_rate_rise_and_rest():
    hr = np.concatenate([np.full(10, 70.0), np.linspace(70, 150, 100)])

    blunted = blunt(hr, np.random.default_rng(0))

    assert blunted[0] < hr[0]
    assert blunted[-1] - blunted[0] < hr[-1] - hr[0]


@needs_prospie
def test_twin_beats_plain_ectemp_on_real_blunted_trials():
    from thermotwin.real_ablation import run

    summary = run()
    twin, plain = summary.loc["ThermoTwin (medication-aware)"], summary.loc["ECTemp (HR only)"]

    assert twin["rmse_c"] < plain["rmse_c"]
    assert twin["danger_sensitivity"] > plain["danger_sensitivity"]
