"""Tests for Tier-0 no-wearable heat-risk module."""

import pytest
from fastapi.testclient import TestClient

from thermotwin.nowearable import RiskTier, Tier0Risk, tier0_risk

# -- Unit tests for tier0_risk -----------------------------------------------

def test_high_risk_returns_alert():
    """Hot + humid + peak hour + heat drug should trigger alert."""
    result = tier0_risk(
        air_temp_c=40.0,
        relative_humidity_pct=80.0,
        hour=13.0,
        age=55,
        bmi=26.0,
        occupation="Construction worker",
        has_heat_illness_drug=True,
    )
    assert result.alert is True
    assert result.risk_score >= 0.5
    assert result.tier == RiskTier.TIER0_NO_WEARABLE


def test_low_risk_no_alert():
    """Mild weather + morning + no drug should not trigger alert."""
    result = tier0_risk(
        air_temp_c=22.0,
        relative_humidity_pct=40.0,
        hour=8.0,
        age=30,
        bmi=22.0,
        occupation="Street vendor",
        has_heat_illness_drug=False,
    )
    assert result.alert is False
    assert result.risk_score < 0.5


def test_tier0_risk_returns_tier0():
    result = tier0_risk(
        air_temp_c=35.0,
        relative_humidity_pct=60.0,
        hour=10.0,
        age=40,
        bmi=24.0,
        occupation="Delivery rider",
        has_heat_illness_drug=False,
    )
    assert result.tier == RiskTier.TIER0_NO_WEARABLE
    assert isinstance(result, Tier0Risk)
    assert 0.0 <= result.risk_score <= 1.0


# -- Endpoint test -----------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from thermotwin.api.main import app
    return TestClient(app)


def test_tier0_endpoint_returns_200(client):
    resp = client.get("/tier0", params={
        "air_temp_c": 40.0,
        "humidity_pct": 75.0,
        "hour": 13.0,
        "age": 45,
        "bmi": 25.0,
        "occupation": "Construction worker",
        "has_heat_drug": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "wbgt_c" in data
    assert "risk_score" in data
    assert "alert" in data
    assert "tier" in data
    assert "reasons" in data
    assert data["tier"] == "tier0_no_wearable"
