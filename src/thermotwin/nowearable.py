"""Tier-0 heat-risk estimate for workers without a wearable.

When no heart-rate data is available, the twin falls back to a
weather-and-demographics model that estimates heat-strain risk from:
  - Air temperature and humidity (WBGT proxy)
  - Age and BMI (physiological vulnerability)
  - Occupation (activity intensity proxy: construction > delivery > vendor)
  - Medication class (any heat-illness drug → elevated baseline risk)
  - Time of day (peak 12:00-15:00)

This is Tier 0; the full medication-aware ECTemp twin is Tier 1.
Tier 0 gives a population-level alert, not a personalised estimate.
"""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

DANGER_WBGT_C = 32.0   # NIOSH action limit for moderate work
PEAK_HOUR_START = 12
PEAK_HOUR_END = 15

class RiskTier(StrEnum):
    TIER0_NO_WEARABLE = "tier0_no_wearable"
    TIER1_WEARABLE = "tier1_wearable"

OCCUPATION_PAR = {
    "Construction worker": 3.2,
    "Farm labourer": 3.0,
    "Delivery rider": 2.6,
    "Street vendor": 2.2,
}
DEFAULT_PAR = 2.8

@dataclass(frozen=True)
class Tier0Risk:
    wbgt_c: float
    risk_score: float       # 0-1, higher = more at risk
    alert: bool
    tier: RiskTier
    reasons: tuple[str, ...]

def wbgt_approximation(air_temp_c: float, relative_humidity_pct: float) -> float:
    """Simplified outdoor WBGT (no solar load): 0.7*Tw + 0.3*Tdb."""
    # Stull (2011) wet-bulb approximation
    tw = air_temp_c * np.arctan(0.151977 * (relative_humidity_pct + 8.313659) ** 0.5) \
         + np.arctan(air_temp_c + relative_humidity_pct) \
         - np.arctan(relative_humidity_pct - 1.676331) \
         + 0.00391838 * relative_humidity_pct ** 1.5 * np.arctan(0.023101 * relative_humidity_pct) \
         - 4.686035
    return 0.7 * tw + 0.3 * air_temp_c

def tier0_risk(
    air_temp_c: float,
    relative_humidity_pct: float,
    hour: float,
    age: int,
    bmi: float,
    occupation: str,
    has_heat_illness_drug: bool,
) -> Tier0Risk:
    """Population-level heat-risk for a worker without a wearable."""
    wbgt = wbgt_approximation(air_temp_c, relative_humidity_pct)

    score = 0.0
    reasons: list[str] = []

    # WBGT contribution
    if wbgt >= DANGER_WBGT_C:
        score += 0.4
        reasons.append(f"WBGT ≈ {wbgt:.1f} °C (≥ {DANGER_WBGT_C} °C NIOSH action limit)")
    elif wbgt >= DANGER_WBGT_C - 3:
        score += 0.2
        reasons.append(f"WBGT ≈ {wbgt:.1f} °C (approaching action limit)")

    # Peak hour
    if PEAK_HOUR_START <= hour < PEAK_HOUR_END:
        score += 0.2
        reasons.append(f"Peak heat hours ({PEAK_HOUR_START}:00-{PEAK_HOUR_END}:00)")

    # Age (>50 higher risk)
    if age >= 50:
        score += 0.1
        reasons.append(f"Age {age} (≥50: reduced heat tolerance)")

    # High-intensity occupation
    par = OCCUPATION_PAR.get(occupation, DEFAULT_PAR)
    if par >= 3.0:
        score += 0.15
        reasons.append(f"{occupation} (high metabolic load, PAR ≈ {par})")

    # Medication
    if has_heat_illness_drug:
        score += 0.15
        reasons.append("On heat-illness-associated medication")

    return Tier0Risk(
        wbgt_c=round(wbgt, 2),
        risk_score=round(min(score, 1.0), 3),
        alert=score >= 0.5,
        tier=RiskTier.TIER0_NO_WEARABLE,
        reasons=tuple(reasons),
    )
