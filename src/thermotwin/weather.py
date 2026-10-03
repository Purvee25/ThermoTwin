"""Historical hourly weather from Open-Meteo (CC BY 4.0), interpolated to minutes.

The default replay is the Delhi heatwave of 20 May - 2 June 2024 (peaks of 46 °C).
Data is cached under data/weather so runs are reproducible offline.
"""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

import numpy as np

from thermotwin import paths

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation"
CACHE_DIR = paths.DATA_DIR / "weather"
KMH_TO_MS = 1 / 3.6
MIN_WIND_M_S = 0.5
HOURS_PER_DAY = 24


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float


DELHI = Location("delhi", 28.61, 77.21)


@dataclass(frozen=True)
class DayWeather:
    """One day of hourly weather; `at` linearly interpolates to fractional hours."""

    date: str
    temp_c: tuple[float, ...]
    rh: tuple[float, ...]
    wind_m_s: tuple[float, ...]
    solar_w_m2: tuple[float, ...]

    def _interp(self, series: tuple[float, ...], hour: float) -> float:
        return float(np.interp(hour, np.arange(HOURS_PER_DAY), series))

    def at(self, hour: float) -> tuple[float, float]:
        return self._interp(self.temp_c, hour), self._interp(self.rh, hour)

    def wind_at(self, hour: float) -> float:
        return max(self._interp(self.wind_m_s, hour), MIN_WIND_M_S)

    def solar_at(self, hour: float) -> float:
        return self._interp(self.solar_w_m2, hour)

    @property
    def max_temp_c(self) -> float:
        return max(self.temp_c)


def fetch_days(location: Location, start: str, end: str) -> list[DayWeather]:
    """Load hourly weather for [start, end] (YYYY-MM-DD), using the cache when present."""
    cache = CACHE_DIR / f"{location.name}_{start}_{end}.json"
    if not cache.exists():
        query = urllib.parse.urlencode(
            {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "start_date": start,
                "end_date": end,
                "hourly": HOURLY_VARS,
                "timezone": "Asia/Kolkata",
            }
        )
        with urllib.request.urlopen(f"{ARCHIVE_URL}?{query}", timeout=30) as response:
            payload = json.load(response)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload["hourly"]))

    hourly = json.loads(cache.read_text())
    n_days = len(hourly["time"]) // HOURS_PER_DAY
    days = []
    for d in range(n_days):
        day = slice(d * HOURS_PER_DAY, (d + 1) * HOURS_PER_DAY)
        days.append(
            DayWeather(
                date=hourly["time"][day.start][:10],
                temp_c=tuple(hourly["temperature_2m"][day]),
                rh=tuple(hourly["relative_humidity_2m"][day]),
                wind_m_s=tuple(v * KMH_TO_MS for v in hourly["wind_speed_10m"][day]),
                solar_w_m2=tuple(hourly["shortwave_radiation"][day]),
            )
        )
    return days


def delhi_heatwave_2024() -> list[DayWeather]:
    return fetch_days(DELHI, "2024-05-20", "2024-06-02")
