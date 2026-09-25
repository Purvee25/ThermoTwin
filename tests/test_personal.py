import numpy as np
import pytest

from thermotwin.personal import MIN_READINGS, PersonalBias, simulated_readings


def test_no_correction_until_enough_readings():
    bias = PersonalBias().add_shift(np.full(100, 37.5), {30: 37.0})

    assert len(bias.readings) < MIN_READINGS
    assert bias.bias_c == 0.0


def test_learns_and_removes_systematic_offset():
    true_core = np.linspace(37.0, 38.2, 200)
    biased_estimate = true_core - 0.3
    bias = PersonalBias()
    for _ in range(3):
        bias.add_shift(biased_estimate, {30: true_core[30], 90: true_core[90], 150: true_core[150]})

    corrected = bias.correct(biased_estimate)

    assert bias.bias_c == pytest.approx(-0.3)
    np.testing.assert_allclose(corrected, true_core)


def test_readings_outside_shift_are_ignored():
    bias = PersonalBias().add_shift(np.full(50, 37.2), {10: 37.0, 400: 39.0, -1: 39.0})

    assert len(bias.readings) == 1


def test_simulated_readings_are_noisy_but_centred():
    core = np.full(200, 37.6)
    rng = np.random.default_rng(0)

    values = [v for _ in range(300) for v in simulated_readings(core, rng).values()]

    assert np.mean(values) == pytest.approx(37.6, abs=0.03)
    assert 0.2 < np.std(values) < 0.4
