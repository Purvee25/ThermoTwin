from dataclasses import replace

import pytest

from thermotwin.ablation import run
from thermotwin.cohort import generate_cohort
from thermotwin.medication import DrugClass
from thermotwin.simulator import PRE_SHIFT_REST_MIN, SHIFT_MIN, simulate_shift


def test_cohort_is_reproducible_and_consistent():
    first, second = generate_cohort(10, seed=3), generate_cohort(10, seed=3)

    assert first == second
    for patient in first:
        drug_blunts_hr = patient.hidden.hr_rise_retained < 1.0
        assert drug_blunts_hr == patient.on_beta_blocker


def test_cohort_rejects_non_positive_size():
    with pytest.raises(ValueError):
        generate_cohort(0)


def test_shift_is_deterministic_and_complete():
    patient = generate_cohort(1, seed=5)[0]

    a, b = simulate_shift(patient, seed=9), simulate_shift(patient, seed=9)

    assert a.equals(b)
    assert len(a) == PRE_SHIFT_REST_MIN + SHIFT_MIN
    assert not a.isna().any().any()


def test_core_temperature_rises_during_hot_shift():
    shift = simulate_shift(generate_cohort(1, seed=5)[0], seed=1)

    assert shift["core_temp_c"].max() > shift["core_temp_c"].iloc[PRE_SHIFT_REST_MIN] + 0.3


def test_beta_blocker_blunts_heart_rate_but_not_core_temperature():
    base = generate_cohort(1, seed=5)[0]
    off_drug = replace(
        base, hidden=replace(base.hidden, hr_rise_retained=1.0, resting_hr_ratio=1.0)
    )
    on_drug = replace(
        base,
        medications=base.medications | {DrugClass.BETA_BLOCKER},
        hidden=replace(base.hidden, hr_rise_retained=0.65, resting_hr_ratio=0.87),
    )

    off_shift, on_shift = simulate_shift(off_drug, seed=2), simulate_shift(on_drug, seed=2)

    assert on_shift["heart_rate"].max() < off_shift["heart_rate"].max() - 15
    assert on_shift["core_temp_c"].max() == pytest.approx(off_shift["core_temp_c"].max())


def test_ablation_twin_beats_plain_ectemp_for_beta_blocker_patients(tmp_path):
    summary = run(n_patients=10, seed=7, out_dir=tmp_path).reset_index()
    on_bb = summary[summary["beta_blocker"]].set_index("estimator")

    assert (
        on_bb.loc["ThermoTwin (medication-aware)", "rmse_c"]
        < on_bb.loc["ECTemp (HR only)", "rmse_c"]
    )
    assert (tmp_path / "ablation_beta_blocker.png").exists()
