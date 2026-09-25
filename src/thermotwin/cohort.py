"""Synthetic cohort of outdoor workers with hypertension.

Each patient carries EHR-visible fields (what the twin may read) and hidden
physiology (what only the ground-truth simulator uses). Keeping them separate
stops the twin from being evaluated on information it could never have.
"""

from dataclasses import dataclass

import numpy as np

from thermotwin.medication import DrugClass

BETA_BLOCKER_SHARE = 0.5
NSAID_SHARE = 0.3
FAST_KIDNEY_DECLINE_SHARE = 0.2
EHR_STREAM = 1
OTHER_ANTIHYPERTENSIVES = (
    DrugClass.ACE_INHIBITOR,
    DrugClass.ARB,
    DrugClass.CALCIUM_CHANNEL_BLOCKER,
    DrugClass.THIAZIDE_DIURETIC,
)


@dataclass(frozen=True)
class HiddenPhysiology:
    """Per-person response the twin cannot observe directly."""

    resting_hr_off_drug: float
    hr_rise_retained: float
    resting_hr_ratio: float
    work_intensity_par: float
    clothing_clo: float
    hr_noise_sd: float


@dataclass(frozen=True)
class KidneyRecord:
    """eGFR in mL/min/1.73 m², one year apart."""

    egfr_last_year: float
    egfr_now: float

    @property
    def annual_change_pct(self) -> float:
        return 100 * (self.egfr_now - self.egfr_last_year) / self.egfr_last_year


@dataclass(frozen=True)
class Patient:
    patient_id: str
    age: int
    sex: str
    height_m: float
    weight_kg: float
    medications: frozenset[DrugClass]
    hidden: HiddenPhysiology
    kidney: KidneyRecord

    @property
    def on_beta_blocker(self) -> bool:
        return DrugClass.BETA_BLOCKER in self.medications


def _sample_medications(rng: np.random.Generator, on_beta_blocker: bool) -> frozenset[DrugClass]:
    n_other = rng.integers(1, 3)
    others = rng.choice(len(OTHER_ANTIHYPERTENSIVES), size=n_other, replace=False)
    meds = {OTHER_ANTIHYPERTENSIVES[i] for i in others}
    if DrugClass.ACE_INHIBITOR in meds:
        meds.discard(DrugClass.ARB)  # dual RAAS blockade is avoided in practice
    if on_beta_blocker:
        meds.add(DrugClass.BETA_BLOCKER)
    return frozenset(meds)


def _sample_hidden(rng: np.random.Generator, on_beta_blocker: bool) -> HiddenPhysiology:
    hr_rise_retained, resting_hr_ratio = 1.0, 1.0
    if on_beta_blocker:
        hr_rise_retained = float(np.clip(rng.normal(0.68, 0.07), 0.5, 0.9))
        resting_hr_ratio = float(np.clip(rng.normal(0.87, 0.04), 0.78, 0.96))
    return HiddenPhysiology(
        resting_hr_off_drug=float(np.clip(rng.normal(74, 7), 58, 92)),
        hr_rise_retained=hr_rise_retained,
        resting_hr_ratio=resting_hr_ratio,
        work_intensity_par=float(rng.uniform(2.2, 3.6)),
        clothing_clo=float(rng.uniform(0.5, 1.0)),
        hr_noise_sd=float(rng.uniform(3.0, 6.0)),
    )


def _sample_kidney(rng: np.random.Generator, age: int) -> KidneyRecord:
    last_year = float(np.clip(rng.normal(95 - 0.7 * (age - 30), 14), 35, 125))
    fast = rng.random() < FAST_KIDNEY_DECLINE_SHARE
    change_pct = rng.uniform(-22, -10) if fast else rng.normal(-2, 2.5)
    return KidneyRecord(last_year, last_year * (1 + change_pct / 100))


def generate_cohort(n_patients: int, seed: int = 0) -> list[Patient]:
    """Generate hypertensive outdoor workers, about half on beta-blockers.

    Args:
        n_patients: Number of patients (must be positive).
        seed: Random seed for reproducibility.

    Returns:
        List of patients.
    """
    if n_patients <= 0:
        raise ValueError("n_patients must be positive")
    rng = np.random.default_rng(seed)
    # EHR-only fields use their own stream so physiology draws stay identical across versions.
    ehr_rng = np.random.default_rng([seed, EHR_STREAM])
    patients = []
    for i in range(n_patients):
        on_bb = bool(rng.random() < BETA_BLOCKER_SHARE)
        sex = "male" if rng.random() < 0.85 else "female"
        height = float(rng.normal(1.68 if sex == "male" else 1.55, 0.06))
        bmi = float(np.clip(rng.normal(25.5, 3.5), 18.5, 36))
        age = int(rng.integers(28, 61))
        meds = _sample_medications(rng, on_bb)
        hidden = _sample_hidden(rng, on_bb)
        if ehr_rng.random() < NSAID_SHARE:
            meds = meds | {DrugClass.NSAID}
        patients.append(
            Patient(
                patient_id=f"P{i:04d}",
                age=age,
                sex=sex,
                height_m=height,
                weight_kg=bmi * height**2,
                medications=meds,
                hidden=hidden,
                kidney=_sample_kidney(ehr_rng, age),
            )
        )
    return patients
