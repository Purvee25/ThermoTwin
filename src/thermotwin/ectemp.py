"""Core body temperature estimation from heart rate (ECTemp, Buller et al. 2013).

Reference: Buller MJ et al. "Estimation of human core temperature from sequential
heart rate observations." Physiol Meas 34(7):781-798, 2013.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class ECTempParams:
    """Extended Kalman filter parameters for 1-minute heart-rate observations.

    Defaults are the published ECTemp values. The observation model maps core
    temperature (CT) to expected heart rate: HR = b2*CT^2 + b1*CT + b0.
    """

    ct_initial: float = 37.1
    variance_initial: float = 0.0
    process_variance: float = 0.022**2
    observation_sd: float = 18.88
    b0: float = -7887.1
    b1: float = 384.4286
    b2: float = -4.5714


def expected_heart_rate(core_temp: FloatArray | float, params: ECTempParams) -> FloatArray:
    """Heart rate the ECTemp observation model expects at a given core temperature."""
    ct = np.asarray(core_temp, dtype=np.float64)
    return params.b2 * ct**2 + params.b1 * ct + params.b0


def estimate_core_temperature(
    heart_rate: npt.ArrayLike,
    params: ECTempParams = ECTempParams(),
) -> tuple[FloatArray, FloatArray]:
    """Run the ECTemp extended Kalman filter over a 1-minute heart-rate series.

    Args:
        heart_rate: Heart rate in bpm, one sample per minute.
        params: Filter parameters.

    Returns:
        Tuple of (core temperature estimate in °C, estimate variance), same length as input.

    Raises:
        ValueError: If the series is empty or contains non-finite values.
    """
    hr = np.asarray(heart_rate, dtype=np.float64)
    if hr.size == 0:
        raise ValueError("heart_rate must not be empty")
    if not np.all(np.isfinite(hr)):
        raise ValueError("heart_rate must contain only finite values")

    observation_variance = params.observation_sd**2
    estimates = np.empty_like(hr)
    variances = np.empty_like(hr)
    ct, variance = params.ct_initial, params.variance_initial

    for i, observed in enumerate(hr):
        variance_pred = variance + params.process_variance
        slope = 2 * params.b2 * ct + params.b1
        gain = variance_pred * slope / (slope**2 * variance_pred + observation_variance)
        ct = ct + gain * (observed - float(expected_heart_rate(ct, params)))
        variance = (1 - gain * slope) * variance_pred
        estimates[i], variances[i] = ct, variance

    return estimates, variances
