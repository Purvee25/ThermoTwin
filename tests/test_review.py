from dataclasses import replace

from thermotwin.cohort import KidneyRecord, generate_cohort
from thermotwin.medication import DrugClass
from thermotwin.review import Priority, review_patient

BASE = generate_cohort(1, seed=0)[0]
STABLE_KIDNEY = KidneyRecord(egfr_last_year=90.0, egfr_now=89.0)


def _patient(meds: set[DrugClass], kidney: KidneyRecord = STABLE_KIDNEY):
    return replace(BASE, medications=frozenset(meds), kidney=kidney)


def _codes(review) -> set[str]:
    return {f.code for f in review.findings}


def test_triple_whammy_needs_all_three_drugs():
    full = _patient({DrugClass.THIAZIDE_DIURETIC, DrugClass.ARB, DrugClass.NSAID})
    missing_nsaid = _patient({DrugClass.THIAZIDE_DIURETIC, DrugClass.ARB})

    assert "triple_whammy" in _codes(review_patient(full, heat_minutes=0))
    assert "triple_whammy" not in _codes(review_patient(missing_nsaid, heat_minutes=0))


def test_rapid_egfr_decline_and_low_egfr_are_flagged():
    falling = _patient({DrugClass.ARB}, KidneyRecord(80.0, 70.0))
    low = _patient({DrugClass.ARB}, KidneyRecord(58.0, 57.0))
    stable = _patient({DrugClass.ARB})

    assert "kidney_decline" in _codes(review_patient(falling, 0))
    assert "kidney_decline" in _codes(review_patient(low, 0))
    assert "kidney_decline" not in _codes(review_patient(stable, 0))


def test_beta_blocker_masking_is_flagged():
    review = review_patient(_patient({DrugClass.BETA_BLOCKER}), heat_minutes=0)

    assert "beta_blocker_masking" in _codes(review)


def test_heat_strain_thresholds():
    patient = _patient({DrugClass.THIAZIDE_DIURETIC})

    assert "predicted_heat_strain" not in _codes(review_patient(patient, heat_minutes=5))
    assert "predicted_heat_strain" in _codes(review_patient(patient, heat_minutes=20))


def test_priority_rises_with_findings_and_findings_sorted_by_weight():
    worst = _patient(
        {DrugClass.THIAZIDE_DIURETIC, DrugClass.ACE_INHIBITOR, DrugClass.NSAID},
        KidneyRecord(80.0, 66.0),
    )
    mild = _patient({DrugClass.THIAZIDE_DIURETIC})

    worst_review = review_patient(worst, heat_minutes=120)
    points = [f.points for f in worst_review.findings]

    assert worst_review.priority is Priority.HIGH
    assert points == sorted(points, reverse=True)
    assert review_patient(mild, heat_minutes=0).priority is Priority.LOW
