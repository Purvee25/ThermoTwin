import pytest
from fastapi.testclient import TestClient

from thermotwin.api.main import app, get_service
from thermotwin.api.service import TwinService
from thermotwin.forecast import train_and_save


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    model_path = train_and_save(
        n_patients=6, seed=1, path=tmp_path_factory.mktemp("m") / "f.joblib"
    )
    service = TwinService(model_path=model_path, n_patients=3)
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_meta_reports_real_heatwave_day(client):
    meta = client.get("/meta").json()

    assert meta["date"] == "2024-05-28"
    assert meta["max_air_temp_c"] > 44


def test_patients_are_sorted_by_risk_and_have_flags(client):
    patients = client.get("/patients", params={"minute": 200}).json()

    assert len(patients) == 3
    risks = [p["risk_now"] or 0.0 for p in patients]
    assert risks == sorted(risks, reverse=True)
    assert all(p["status"] in {"red", "amber", "green"} for p in patients)
    assert all(p["flags"] for p in patients)


def test_timeline_has_band_around_estimate(client):
    pid = client.get("/patients").json()[0]["patient_id"]

    points = client.get(f"/patients/{pid}/timeline").json()["points"]

    assert len(points) > 300
    assert all(p["band_low_c"] <= p["twin_core_c"] <= p["band_high_c"] for p in points)


def test_unknown_patient_returns_404(client):
    assert client.get("/patients/NOPE/timeline").status_code == 404
    assert (
        client.post(
            "/patients/NOPE/whatif", json={"start_minute": 100, "duration_min": 20}
        ).status_code
        == 404
    )


def test_whatif_rest_break_does_not_raise_true_heat(client):
    pid = client.get("/patients").json()[0]["patient_id"]

    body = client.post(
        f"/patients/{pid}/whatif", json={"start_minute": 150, "duration_min": 30}
    ).json()

    assert body["scenario"]["true_danger_minutes"] <= body["baseline"]["true_danger_minutes"]


def test_whatif_validates_duration(client):
    pid = client.get("/patients").json()[0]["patient_id"]

    response = client.post(
        f"/patients/{pid}/whatif", json={"start_minute": 100, "duration_min": 500}
    )

    assert response.status_code == 422


def test_review_is_ranked_and_actionable(client):
    items = client.get("/review").json()

    assert len(items) == 3
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)
    for item in items:
        assert item["priority"] in {"high", "medium", "low"}
        assert all(f["action"] and f["evidence"] for f in item["findings"])
