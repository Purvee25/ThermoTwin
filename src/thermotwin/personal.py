"""Per-person learning across shifts: the twin learns each worker's systematic bias.

After each shift the worker takes a few quick thermometer readings (e.g. ear, ±0.3 °C).
The twin compares its own estimates at those minutes with the readings and keeps a
running per-person bias, which it subtracts on the next shift. No reference reading is
needed on the day being predicted.

Tried and rejected on real PROSPIE data: a linear rest + activity + heat heart-rate
model calibrated in the first shift minutes (RMSE 0.49-0.98 °C vs ECTemp 0.36 °C).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from thermotwin.ectemp import FloatArray

READING_MINUTES = (30, 60, 90)
READING_SD_C = 0.3
MIN_READINGS = 2


@dataclass(frozen=True)
class Reading:
    """A reference core reading paired with the twin's own estimate at that minute."""

    twin_estimate_c: float
    thermometer_c: float


@dataclass
class PersonalBias:
    """Running per-person bias between the twin's estimates and reference readings."""

    readings: list[Reading] = field(default_factory=list)

    def add_shift(self, estimates: npt.ArrayLike, thermometer: dict[int, float]) -> "PersonalBias":
        """Record a finished shift's readings as {minute: thermometer °C}."""
        est = np.asarray(estimates, dtype=np.float64)
        for minute, value in thermometer.items():
            if 0 <= minute < est.size:
                self.readings.append(Reading(float(est[minute]), float(value)))
        return self

    @property
    def bias_c(self) -> float:
        """Mean (estimate - reading); zero until enough readings exist."""
        if len(self.readings) < MIN_READINGS:
            return 0.0
        return float(np.mean([r.twin_estimate_c - r.thermometer_c for r in self.readings]))

    def correct(self, estimates: npt.ArrayLike) -> FloatArray:
        return np.asarray(estimates, dtype=np.float64) - self.bias_c


def simulated_readings(
    true_core: npt.ArrayLike,
    rng: np.random.Generator,
    minutes: Iterable[int] = READING_MINUTES,
    sd_c: float = READING_SD_C,
) -> dict[int, float]:
    """Noisy thermometer readings at the given minutes (for validation on known core)."""
    core = np.asarray(true_core, dtype=np.float64)
    return {m: float(core[m] + rng.normal(0, sd_c)) for m in minutes if m < core.size}
