"""Pre-summer medication and heat-vulnerability review for the clinician.

Transparent rules, each tied to evidence, turn the EHR and the twin's heatwave replay
into findings with suggested actions *for clinician review*. The priority score is a
triage heuristic and has not been validated as a clinical score.
"""

from dataclasses import dataclass
from enum import StrEnum

from thermotwin.cohort import Patient
from thermotwin.medication import DrugClass

RAPID_EGFR_DECLINE = 5.0  # mL/min/1.73 m² per year (KDIGO definition of rapid progression)
CKD_STAGE_3_EGFR = 60.0
HIGH_HEAT_MINUTES = 60
MODERATE_HEAT_MINUTES = 15
HIGH_PRIORITY_SCORE = 5
MEDIUM_PRIORITY_SCORE = 3
HEAT_ILLNESS_DRUGS = frozenset({
    DrugClass.ACE_INHIBITOR,
    DrugClass.ARB,
    DrugClass.CALCIUM_CHANNEL_BLOCKER,
    DrugClass.THIAZIDE_DIURETIC,
    DrugClass.LOOP_DIURETIC,
})


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Finding:
    code: str
    title: str
    detail: str
    action: str
    evidence: str
    points: int


@dataclass(frozen=True)
class Review:
    patient_id: str
    priority: Priority
    score: int
    heat_minutes: int
    findings: tuple[Finding, ...]


def _triple_whammy(patient: Patient) -> Finding | None:
    meds = patient.medications
    if not (
        DrugClass.THIAZIDE_DIURETIC in meds
        and meds & {DrugClass.ACE_INHIBITOR, DrugClass.ARB}
        and DrugClass.NSAID in meds
    ):
        return None
    return Finding(
        code="triple_whammy",
        title="Triple-whammy kidney risk",
        detail="Diuretic + ACE inhibitor/ARB + NSAID; dehydration in heat adds to the risk.",
        action="Review NSAID use (consider paracetamol); check creatinine and potassium "
        "before the heat season.",
        evidence="Lapi et al., BMJ 2013;346:e8525",
        points=3,
    )


def _kidney(patient: Patient) -> Finding | None:
    kidney = patient.kidney
    drop = kidney.egfr_last_year - kidney.egfr_now
    if drop < RAPID_EGFR_DECLINE and kidney.egfr_now >= CKD_STAGE_3_EGFR:
        return None
    return Finding(
        code="kidney_decline",
        title="Kidney function falling" if drop >= RAPID_EGFR_DECLINE else "Reduced eGFR",
        detail=f"eGFR {kidney.egfr_last_year:.0f} → {kidney.egfr_now:.0f} mL/min/1.73 m² "
        f"in a year ({kidney.annual_change_pct:+.0f}%). Confirm with a repeat test.",
        action="Recheck eGFR and electrolytes before summer; review diuretic dose and "
        "hydration advice; avoid NSAIDs in heat. Review ACE inhibitor/ARB dose at eGFR < 45.",
        evidence="KDIGO 2024 CKD guideline (rapid progression ≥ 5 mL/min/1.73 m²/yr)",
        points=2,
    )


def _beta_blocker(patient: Patient) -> Finding | None:
    if not patient.on_beta_blocker:
        return None
    return Finding(
        code="beta_blocker_masking",
        title="Heart rate under-reports heat strain",
        detail="Beta-blockers blunt the heart-rate rise that wearables use to estimate heat.",
        action="Do not rely on heart-rate alerts alone; schedule fixed shade breaks.",
        evidence="Casa et al., ACSM 2015 — exertional heat stroke risk factors; "
        "ThermoTwin ablation: HR-only caught 18% vs twin 62% of danger minutes",
        points=1,
    )


def _raas_ccb(patient: Patient) -> Finding | None:
    drugs = sorted(d.value.replace("_", " ") for d in patient.medications & HEAT_ILLNESS_DRUGS)
    if not drugs:
        return None
    return Finding(
        code="heat_illness_drugs",
        title="Higher heat-illness risk in heatwaves",
        detail=f"On {', '.join(drugs)}.",
        action="Counsel on hydration, shade and what to do if dehydrated (sick-day guidance).",
        evidence="Antihypertensives and heat-related illness during heatwaves, 2026 "
        "(doi:10.1002/pds.70447)",
        points=1,
    )


def _heat_strain(heat_minutes: int) -> Finding | None:
    if heat_minutes < MODERATE_HEAT_MINUTES:
        return None
    return Finding(
        code="predicted_heat_strain",
        title="Twin predicts heat strain on heatwave days",
        detail=f"About {heat_minutes} min likely ≥ 38 °C core in the 28 May 2024 Delhi replay.",
        action="Advise avoiding peak hours (12:00 to 15:00) and a shade break every hour.",
        evidence="NDMA heatwave guidelines; ThermoTwin replay",
        points=3 if heat_minutes >= HIGH_HEAT_MINUTES else 1,
    )


def review_patient(patient: Patient, heat_minutes: int) -> Review:
    """Build the pre-summer review for one patient.

    Args:
        patient: Patient with medications and kidney record.
        heat_minutes: Shift minutes the twin judges likely (≥ 50%) to be at ≥ 38 °C core
            during a heatwave replay.

    Returns:
        Review with findings sorted by weight and an overall priority.
    """
    checks = (
        _triple_whammy(patient),
        _kidney(patient),
        _heat_strain(heat_minutes),
        _beta_blocker(patient),
        _raas_ccb(patient),
    )
    findings = tuple(sorted((f for f in checks if f), key=lambda f: -f.points))
    score = sum(f.points for f in findings)
    if score >= HIGH_PRIORITY_SCORE:
        priority = Priority.HIGH
    elif score >= MEDIUM_PRIORITY_SCORE:
        priority = Priority.MEDIUM
    else:
        priority = Priority.LOW
    return Review(patient.patient_id, priority, score, heat_minutes, findings)
