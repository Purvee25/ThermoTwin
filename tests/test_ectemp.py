import numpy as np
import pytest

from thermotwin.ectemp import ECTempParams, estimate_core_temperature, expected_heart_rate

PARAMS = ECTempParams()


def test_steady_heart_rate_converges_to_matching_core_temperature():
    target = 38.0
    hr = np.full(400, float(expected_heart_rate(target, PARAMS)))

    estimate, _ = estimate_core_temperature(hr)

    assert estimate[-1] == pytest.approx(target, abs=0.05)


def test_output_shapes_and_variance_are_valid():
    hr = np.linspace(75, 130, 120)

    estimate, variance = estimate_core_temperature(hr)

    assert estimate.shape == hr.shape == variance.shape
    assert np.all(variance >= 0)


def test_higher_heart_rate_gives_higher_estimate():
    low, _ = estimate_core_temperature(np.full(200, 90.0))
    high, _ = estimate_core_temperature(np.full(200, 130.0))

    assert high[-1] > low[-1]


@pytest.mark.parametrize("bad", [[], [80.0, np.nan, 90.0], [80.0, np.inf]])
def test_rejects_empty_or_non_finite_input(bad):
    with pytest.raises(ValueError):
        estimate_core_temperature(bad)
