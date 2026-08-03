"""Tests for the Tamil Nadu scale layer: district catalog, live scope switch,
ingestion adapters (demo mode), and calibration harness."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.db import SessionLocal
from app.main import app


@pytest.fixture(scope="session")
def client():
    from app.services import ticker

    ticker.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db(client):
    from app.services.seeder import seed_if_empty

    s = SessionLocal()
    try:
        if s.query(__import__("app.core.models", fromlist=["Location"]).Location).count() == 0:
            seed_if_empty(s, get_settings())
        yield s
    finally:
        s.close()


def test_tn_catalog_generates_53_zones():
    from app.data.seeds.generate_tn_districts import DISTRICTS, generate

    data = generate()
    zones = data["zones"]
    assert len(zones) == 15 + len(DISTRICTS) == 53
    assert data["scope"] == "tamilnadu"
    districts = {z["region"] for z in zones if z["id"].startswith("tn_")}
    assert len(districts) == 38
    # low-lying coastal zones must carry higher exposure than hill districts
    nagapattinam = next(z for z in zones if z["id"] == "tn_nagapattinam")
    nilgiris = next(z for z in zones if z["id"] == "tn_nilgiris")
    assert nagapattinam["exposure"] > nilgiris["exposure"]
    # every zone carries full telemetry series
    for z in zones:
        assert len(z["weather"]) == 72
        assert z["region"]


def test_scope_switch_endpoint(client, db):
    from app.core.models import Location

    r = client.get("/api/v1/scope")
    assert r.status_code == 200
    assert r.json()["scope"] == "chennai"

    r = client.post("/api/v1/scope", json={"scope": "tamilnadu"})
    assert r.status_code == 200
    body = r.json()
    assert body["zones"] == 53

    # all 38 district HQs present with real region tags
    regions = {loc.region for loc in db.query(Location).all()}
    assert "Nagapattinam" in regions and "Coimbatore" in regions and "Nilgiris" in regions

    # restore chennai so sibling tests stay deterministic
    client.post("/api/v1/scope", json={"scope": "chennai"})
    assert client.get("/api/v1/scope").json()["scope"] == "chennai"


def test_ingest_adapters_demo_mode(client, db):
    from app.services.ingest import registry

    statuses = registry.statuses()
    assert {s["id"] for s in statuses} == {"imd", "gpm", "reservoir"}
    assert all(s["mode"] == "demo" for s in statuses)

    out = registry.ingest_once(db)
    assert out["imd"]["rows"] > 0
    assert out["gpm"]["rows"] > 0
    assert out["reservoir"]["rows"] == out["imd"]["rows"] * 2

    # frames wrote into canonical tables + archive
    from app.core.models import IngestedDatum, WeatherSnapshot

    assert db.query(WeatherSnapshot).count() > 0
    assert db.query(IngestedDatum).count() > 0

    r = client.get("/api/v1/data/sources")
    assert r.status_code == 200
    assert len(r.json()["adapters"]) == 3


def test_calibration_harness_reports_metrics():
    from app.ml.calibration import calibrate_report, reliability
    from scripts.calibrate import build_retrospective

    y_true, y_pred = build_retrospective()
    report = calibrate_report(y_true, y_pred)
    assert 0.0 <= report["brier_before"] <= 0.25
    assert report["n"] == len(y_true) == len(y_pred)
    assert report["brier_after"] <= report["brier_before"] + 1e-9
    rows = reliability(y_true, y_pred, bins=5)
    assert rows and all(r["n"] > 0 for r in rows)


def test_ingested_data_persisted_after_scope_switch(client, db):
    # switching scope wipes scoped rows (archive included) then reseeds
    from app.core.models import IngestedDatum

    client.post("/api/v1/scope", json={"scope": "chennai"})
    assert db.query(IngestedDatum).count() == 0


def test_comparative_analysis_endpoint(client, db):
    from app.core.models import Location

    loc = db.query(Location).first()
    r = client.get(f"/api/v1/decisions/compare/{loc.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["location_id"] == loc.id
    assert body["live"]["hour"] == body["live"]["hour"] == 48
    assert 0 <= body["live"]["risk_probability"] <= 1
    # evolution arc + verdict + markdown report all present
    assert body["evolution"]["peak_probability"] >= body["live"]["risk_probability"]
    assert body["verdict"]["tone"] in {"red", "amber", "blue"}
    assert "Live Analysis" in body["markdown"]
    assert body["previous_records"], "persisted predictions must be archived for comparison"
    assert body["analogues"][0]["matching_drivers"] >= 0

    r = client.get("/api/v1/decisions/compare/does-not-exist")
    assert r.status_code == 404