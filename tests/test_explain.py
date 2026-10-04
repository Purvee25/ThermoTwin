"""Tests for the SHAP /explain endpoint and explain_prediction helper."""

import pytest
from fastapi.testclient import TestClient

from thermotwin.api.main import app, get_service
from thermotwin.api.service import TwinService
from thermotwin.forecast import FEATURES, explain_prediction, new_forecaster, train_and_save


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    model_path = train_and_save(
        n_patients=6, seed=7, path=tmp_path_factory.mktemp("m") / "f.joblib"
    )
    service = TwinService(model_path=model_path, n_patients=3)
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app), service
    app.dependency_overrides.clear()


def test_explain_endpoint_returns_top5(client):
    tc, service = client
    patient_id = next(iter(service._patients))
    resp = tc.get(f"/patients/{patient_id}/explain")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["patient_id"] == patient_id
    assert isinstance(body["minute"], int)
    assert 0.0 <= body["risk_60"] <= 1.0
    assert len(body["top_features"]) == 5
    for feat in body["top_features"]:
        assert feat["feature"] in FEATURES
        assert isinstance(feat["contribution"], float)
        assert 0.0 <= feat["contribution_pct"] <= 100.0


def test_explain_endpoint_unknown_patient(client):
    tc, _ = client
    resp = tc.get("/patients/P9999/explain")
    assert resp.status_code == 404


def test_explain_prediction_helper():
    """Unit test for explain_prediction: returns ranked contributions for all features."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(42)
    model = new_forecaster(seed=42)
    n = 50
    X = pd.DataFrame(rng.random((n, len(FEATURES))), columns=FEATURES)
    y = rng.integers(0, 2, size=n)
    model.fit(X, y)

    row = X.iloc[[0]]
    result = explain_prediction(model, row, FEATURES)

    assert len(result) == len(FEATURES)
    # Sorted by descending |contribution|
    abs_contribs = [abs(r["contribution"]) for r in result]
    assert abs_contribs == sorted(abs_contribs, reverse=True)
    # All feature names present
    assert {r["feature"] for r in result} == set(FEATURES)
