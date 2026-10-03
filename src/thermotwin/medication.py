"""Medication-aware correction of heart-rate input before core temperature estimation.

Beta-blockers lower resting heart rate and blunt the rise in heart rate with heat
and work, so an unmodified ECTemp filter under-reads core temperature for these
patients. The twin reverses the blunting using population priors, not the
patient's true (unknown) response, and widens the observation noise to reflect
the extra uncertainty.
"""

from dataclasses import dataclass, replace
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from thermotwin.ectemp import ECTempParams, FloatArray, estimate_core_temperature

RESTING_WINDOW_MIN = 10


class DrugClass(StrEnum):
    BETA_BLOCKER = "beta_blocker"
    ACE_INHIBITOR = "ace_inhibitor"
    ARB = "arb"
    CALCIUM_CHANNEL_BLOCKER = "calcium_channel_blocker"
    THIAZIDE_DIURETIC = "thiazide_diuretic"
    LOOP_DIURETIC = "loop_diuretic"
    NSAID = "nsaid"


@dataclass(frozen=True)
class BetaBlockerPrior:
    """Population-level beta-blocker effects on heart rate.

    hr_rise_retained: fraction of the normal heart-rate rise (above rest) that remains.
    resting_hr_ratio: resting heart rate on the drug relative to off it.
    observation_sd_inflation: multiplier on ECTemp observation noise.
    """

    hr_rise_retained: float = 0.70
    resting_hr_ratio: float = 0.88
    observation_sd_inflation: float = 1.5


def estimate_resting_heart_rate(heart_rate: FloatArray, window: int = RESTING_WINDOW_MIN) -> float:
    """Resting heart rate as the median of the first `window` minutes (pre-shift rest)."""
    if heart_rate.size < window:
        raise ValueError(f"need at least {window} minutes of heart rate to estimate rest")
    return float(np.median(heart_rate[:window]))


def unblunt_heart_rate(
    heart_rate: npt.ArrayLike,
    resting_hr: float,
    prior: BetaBlockerPrior = BetaBlockerPrior(),
) -> FloatArray:
    """Map a beta-blocked heart-rate series to what it would be off the drug."""
    hr = np.asarray(heart_rate, dtype=np.float64)
    resting_off_drug = resting_hr / prior.resting_hr_ratio
    return resting_off_drug + (hr - resting_hr) / prior.hr_rise_retained


def twin_core_temperature(
    heart_rate: npt.ArrayLike,
    medications: frozenset[DrugClass],
    params: ECTempParams = ECTempParams(),
    prior: BetaBlockerPrior = BetaBlockerPrior(),
) -> tuple[FloatArray, FloatArray]:
    """Core temperature estimate that adapts to the patient's medication record.

    Args:
        heart_rate: 1-minute heart rate in bpm; the first minutes must be at rest.
        medications: Drug classes from the patient's EHR.
        params: Base ECTemp parameters.
        prior: Beta-blocker population prior.

    Returns:
        Tuple of (core temperature estimate in °C, estimate variance).
    """
    hr = np.asarray(heart_rate, dtype=np.float64)
    if DrugClass.BETA_BLOCKER not in medications:
        return estimate_core_temperature(hr, params)

    corrected = unblunt_heart_rate(hr, estimate_resting_heart_rate(hr), prior)
    widened = replace(params, observation_sd=params.observation_sd * prior.observation_sd_inflation)
    return estimate_core_temperature(corrected, widened)
