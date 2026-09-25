"""Ground-truth shift simulator.

Core and skin temperature come from JOS-3 (a multi-node thermoregulation model).
Heart rate is generated from a separate linear physiology model, not the ECTemp
quadratic, so the twin is never tested against its own assumptions.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd
from pythermalcomfort.models import JOS3

from thermotwin.cohort import Patient

PRE_SHIFT_REST_MIN = 20
SHIFT_MIN = 360
SHIFT_START_HOUR = 11.0
REST_PAR = 1.2
WAITING_PAR = 1.6
BREAK_EVERY_MIN = 120
BREAK_MIN = 15
WIND_M_S = 1.5
SUN_RADIANT_OFFSET_C = 8.0
REFERENCE_SOLAR_W_M2 = 800.0
INDOOR_TEMP_C = 31.0
INDOOR_RH = 50.0

HR_PER_PAR = 12.0
HR_PER_CORE_C = 33.0
HR_PER_SKIN_C = 2.5
SKIN_HR_THRESHOLD_C = 34.0
HR_AR_COEF = 0.8
HR_MIN, HR_MAX = 40.0, 200.0


class Weather(Protocol):
    def at(self, hour: float) -> tuple[float, float]: ...
    def wind_at(self, hour: float) -> float: ...
    def solar_at(self, hour: float) -> float: ...


@dataclass(frozen=True)
class HeatDay:
    """Diurnal outdoor weather: temperature peaks mid-afternoon, humidity is lowest then."""

    t_min_c: float = 31.0
    t_max_c: float = 45.0
    rh_min: float = 18.0
    rh_max: float = 45.0
    peak_hour: float = 15.0

    def at(self, hour: float) -> tuple[float, float]:
        phase = np.cos(2 * np.pi * (hour - self.peak_hour) / 24)
        weight = (phase + 1) / 2
        temp = self.t_min_c + (self.t_max_c - self.t_min_c) * weight
        rh = self.rh_max - (self.rh_max - self.rh_min) * weight
        return float(temp), float(rh)

    def wind_at(self, hour: float) -> float:
        return WIND_M_S

    def solar_at(self, hour: float) -> float:
        return REFERENCE_SOLAR_W_M2


def activity_schedule(work_par: float, rng: np.random.Generator) -> np.ndarray:
    """Per-minute metabolic activity (PAR): pre-shift rest, then rides, waits and breaks."""
    par = np.full(PRE_SHIFT_REST_MIN + SHIFT_MIN, REST_PAR)
    minute = PRE_SHIFT_REST_MIN
    end = PRE_SHIFT_REST_MIN + SHIFT_MIN
    while minute < end:
        ride = int(rng.integers(12, 26))
        wait = int(rng.integers(3, 9))
        par[minute : minute + ride] = work_par
        par[minute + ride : minute + ride + wait] = WAITING_PAR
        minute += ride + wait
    for start in range(PRE_SHIFT_REST_MIN + BREAK_EVERY_MIN, end, BREAK_EVERY_MIN):
        par[start : start + BREAK_MIN] = REST_PAR
    return par


def _heart_rate(
    patient: Patient,
    par: np.ndarray,
    core: np.ndarray,
    skin: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    hidden = patient.hidden
    rise = (
        HR_PER_PAR * (par - 1.0)
        + HR_PER_CORE_C * (core - core[0])
        + HR_PER_SKIN_C * np.maximum(skin - SKIN_HR_THRESHOLD_C, 0.0)
    )
    true_hr = hidden.resting_hr_off_drug * hidden.resting_hr_ratio + rise * hidden.hr_rise_retained

    noise = np.empty_like(true_hr)
    noise[0] = rng.normal(0, hidden.hr_noise_sd)
    innovation_sd = hidden.hr_noise_sd * np.sqrt(1 - HR_AR_COEF**2)
    for i in range(1, noise.size):
        noise[i] = HR_AR_COEF * noise[i - 1] + rng.normal(0, innovation_sd)
    return np.clip(true_hr + noise, HR_MIN, HR_MAX)


def simulate_shift(
    patient: Patient,
    weather: Weather = HeatDay(),
    seed: int = 0,
    extra_rest: Sequence[tuple[int, int]] = (),
) -> pd.DataFrame:
    """Simulate one work shift minute by minute.

    Args:
        patient: Worker to simulate.
        weather: Outdoor weather (synthetic HeatDay or a real DayWeather replay).
        seed: Random seed for activity and heart-rate noise.
        extra_rest: Additional rest breaks as (start minute, duration) for what-if scenarios.

    Returns:
        DataFrame with columns minute, hour, air_temp_c, rh, par, core_temp_c,
        skin_temp_c, heart_rate. Minutes before PRE_SHIFT_REST_MIN are indoor rest.
    """
    rng = np.random.default_rng(seed)
    par = activity_schedule(patient.hidden.work_intensity_par, rng)
    for start, duration in extra_rest:
        par[max(start, 0) : start + duration] = REST_PAR
    n = par.size
    model = JOS3(
        height=patient.height_m,
        weight=patient.weight_kg,
        age=patient.age,
        sex=patient.sex,
    )
    pelvis = model.body_names.index("pelvis")
    model.clo = patient.hidden.clothing_clo

    hours = SHIFT_START_HOUR + (np.arange(n) - PRE_SHIFT_REST_MIN) / 60
    air, rh = np.empty(n), np.empty(n)
    core, skin = np.empty(n), np.empty(n)
    for i in range(n):
        outdoors = i >= PRE_SHIFT_REST_MIN
        air[i], rh[i] = weather.at(hours[i]) if outdoors else (INDOOR_TEMP_C, INDOOR_RH)
        solar_gain = weather.solar_at(hours[i]) / REFERENCE_SOLAR_W_M2 if outdoors else 0.0
        model.tdb, model.rh, model.par = air[i], rh[i], par[i]
        model.v = weather.wind_at(hours[i]) if outdoors else WIND_M_S
        model.tr = air[i] + SUN_RADIANT_OFFSET_C * solar_gain
        model.simulate(times=1, dtime=60)
        core[i] = model.t_core[pelvis]
        skin[i] = model.t_skin_mean

    return pd.DataFrame(
        {
            "minute": np.arange(n),
            "hour": hours,
            "air_temp_c": air,
            "rh": rh,
            "par": par,
            "core_temp_c": core,
            "skin_temp_c": skin,
            "heart_rate": _heart_rate(patient, par, core, skin, rng),
        }
    )
