"""API response and request models."""

from typing import Literal

from pydantic import BaseModel, Field

RiskStatus = Literal["red", "amber", "green"]


class MedicationFlag(BaseModel):
    drug_class: str
    note: str


class PatientSummary(BaseModel):
    patient_id: str
    name: str
    age: int
    sex: str
    occupation: str
    medications: list[str]
    flags: list[MedicationFlag]
    learned_bias_c: float = Field(description="Twin's learned per-person bias (°C)")
    risk_now: float | None = Field(description="ML forecast: P(core >= 38 °C within 60 min)")
    p_above_now: float | None = Field(description="P(core >= 38 °C now) from the twin estimate")
    peak_risk: float
    status: RiskStatus
    first_alert_clock: str | None


class TimelinePoint(BaseModel):
    minute: int
    clock: str
    twin_core_c: float
    band_low_c: float
    band_high_c: float
    true_core_c: float = Field(description="Simulation ground truth, shown for validation only")
    heart_rate: float
    air_temp_c: float
    activity_par: float
    risk_60: float | None
    p_above_now: float
    alert: bool


class Timeline(BaseModel):
    patient_id: str
    date: str
    danger_core_c: float
    points: list[TimelinePoint]


class WhatIfRequest(BaseModel):
    start_minute: int = Field(ge=0, description="Minute of the shift timeline to start resting")
    duration_min: int = Field(ge=5, le=60)


class ScenarioSummary(BaseModel):
    peak_twin_core_c: float
    alert_minutes: int
    true_danger_minutes: int


class WhatIfResponse(BaseModel):
    baseline: ScenarioSummary
    scenario: ScenarioSummary
    timeline: Timeline


class Meta(BaseModel):
    location: str
    date: str
    max_air_temp_c: float
    danger_core_c: float
    alert_probability: float
    disclaimer: str
