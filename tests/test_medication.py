import numpy as np
import pytest

from thermotwin.ectemp import estimate_core_temperature
from thermotwin.medication import (
    RESTING_WINDOW_MIN,
    BetaBlockerPrior,
    DrugClass,
    estimate_resting_heart_rate,
    twin_core_temperature,
    unblunt_heart_rate,
)

PRIOR = BetaBlockerPrior()
RESTING_OFF_DRUG = 75.0


def _shift_heart_rate() -> np.ndarray:
    rest = np.full(RESTING_WINDOW_MIN, RESTING_OFF_DRUG)
    work = np.linspace(RESTING_OFF_DRUG, 135.0, 300)
    return np.concatenate([rest, work])


def _blunt(off_drug: np.ndarray, prior: BetaBlockerPrior) -> np.ndarray:
    resting_on_drug = RESTING_OFF_DRUG * prior.resting_hr_ratio
    return resting_on_drug + (off_drug - RESTING_OFF_DRUG) * prior.hr_rise_retained


def test_unblunt_recovers_off_drug_heart_rate_when_prior_matches():
    off_drug = _shift_heart_rate()
    blunted = _blunt(off_drug, PRIOR)

    recovered = unblunt_heart_rate(blunted, estimate_resting_heart_rate(blunted), PRIOR)

    np.testing.assert_allclose(recovered, off_drug, rtol=1e-9)


def test_without_beta_blocker_twin_matches_plain_ectemp():
    hr = _shift_heart_rate()
    meds = frozenset({DrugClass.ACE_INHIBITOR, DrugClass.THIAZIDE_DIURETIC})

    twin, _ = twin_core_temperature(hr, meds)
    plain, _ = estimate_core_temperature(hr)

    np.testing.assert_array_equal(twin, plain)


def test_beta_blocker_record_raises_estimate_for_blunted_heart_rate():
    blunted = _blunt(_shift_heart_rate(), PRIOR)

    twin, _ = twin_core_temperature(blunted, frozenset({DrugClass.BETA_BLOCKER}))
    plain, _ = estimate_core_temperature(blunted)

    assert twin[-1] > plain[-1]


def test_beta_blocker_widens_uncertainty():
    blunted = _blunt(_shift_heart_rate(), PRIOR)

    _, twin_var = twin_core_temperature(blunted, frozenset({DrugClass.BETA_BLOCKER}))
    _, plain_var = estimate_core_temperature(blunted)

    assert twin_var[-1] > plain_var[-1]


def test_resting_estimate_needs_enough_minutes():
    with pytest.raises(ValueError):
        estimate_resting_heart_rate(np.full(RESTING_WINDOW_MIN - 1, 70.0))
