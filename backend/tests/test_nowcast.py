"""Phase 1 — lead-aware forecast core tests.

The old forecaster extrapolated the realized probability line, so an incoming
storm ramp (already latent in the rain forecast) was invisible until it
accumulated. These tests lock in the two-stage nowcast: forward-signal fusion
into a short-horizon ladder, and honest verification of that ladder.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from app.services import ticker

    ticker.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def seeded(client):
    from app.config import get_settings
    from app.core.db import SessionLocal
    from app.services.seeder import seed_if_empty

    db = SessionLocal()
    try:
        if db.query(__import__("app.core.models", fromlist=["Location"]).Location).count() == 0:
            seed_if_empty(db, get_settings())
        yield db
    finally:
        db.close()


def _flood_comps():
    return {
        "rain_intensity": 2.0, "soil_moisture": 3.0, "headroom_deficit": 3.0,
        "drainage_stress": 2.0, "citizen_pressure": 1.0,
    }


def test_ladder_shape_and_monotonic_risk():
    from app.services.nowcast import LEADS, lead_ladder

    ladder = lead_ladder(_flood_comps(), "flood",
                         {"rain_forecast_mm": 200, "rain6_mm": 10, "inflow_m3s": 15}, exposure=1.0)
    assert [r["lead_h"] for r in ladder] == list(LEADS)
    for rung in ladder:
        assert 0.0 <= rung["probability"] <= 1.0
        assert isinstance(rung["level"], str) and rung["level"]
        assert rung["reasons"], "quiet lead contradicts reason-trail promise"
    # with a strong incoming rain forecast, risk peaks at the +6h forecast
    # validity and *holds* (persistence) for longer leads — never below nowcast
    peak = max(ladder, key=lambda r: r["probability"])
    assert peak["lead_h"] == 6
    assert peak["probability"] >= ladder[0]["probability"]
    assert ladder[-1]["probability"] <= peak["probability"]


def test_forecast_kernel_peaks_at_6h():
    from app.services.nowcast import components_ahead

    comps = _flood_comps()
    feed = {"rain_forecast_mm": 300, "rain6_mm": 10, "inflow_m3s": 0}
    c1, _ = components_ahead(comps, "flood", feed, 1.0, 1)
    c6, _ = components_ahead(comps, "flood", feed, 1.0, 6)
    c24, _ = components_ahead(comps, "flood", feed, 1.0, 24)
    # forecast is +6h-valid — biggest lift at +6h, not before and not 24h out
    assert c6["rain_intensity"] >= c1["rain_intensity"]
    assert c6["rain_intensity"] >= c24["rain_intensity"]
    # calm feed must not inflate anything
    cn, _ = components_ahead(comps, "flood", {"rain_forecast_mm": 0, "rain6_mm": 0, "inflow_m3s": 0}, 1.0, 6)
    assert cn["rain_intensity"] == comps["rain_intensity"]


def test_prediction_agent_emits_ladder(client, seeded):
    from app.api.routes.risks import get_prediction
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        body = get_prediction("mylapore", 24, db)
    finally:
        db.close()
    assert body["lead_ladder"], "prediction route must expose the lead ladder"
    assert all(0.0 <= r["probability"] <= 1.0 for r in body["lead_ladder"])
    assert "peak_in_h" in body and "peak_probability" in body
    assert any(r["reasons"] for r in body["lead_ladder"])


def test_short_history_no_fake_trend():
    from app.ml.forecaster import DEFAULT_FORECASTER

    t0 = datetime.now(timezone.utc)
    fc = DEFAULT_FORECASTER.fit_forecast([0.05], t0, 12)  # one calm sample
    # must not extrapolate 0.05 -> 0.6+ from zero-padding a young series
    assert max(fc.mean) < 0.5
    assert all(0.0 <= v <= 1.0 for v in fc.mean)


def test_verification_returns_legible_signal(client, seeded):
    from app.api.routes.validation import get_validation
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        report = get_validation("chennai", db)
    finally:
        db.close()
    o = report["overall"]
    assert o["brier"] >= 0 and isinstance(o["auc"], float) and 0.5 <= o["auc"] <= 1.0
    assert "calibration" in o and o["calibration"]["mean_forecast"] >= 0
    assert o["reliability"], "reliability table must not be empty"
    assert report["zones"] and all(z["location_id"] for z in report["zones"])


def test_validation_route_http(client, seeded):
    from app.services import ticker

    ticker.set_hour(60)
    resp = client.get("/api/v1/validation?scope=chennai")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall"]["brier"] >= 0
    assert "calibration" in body["overall"]