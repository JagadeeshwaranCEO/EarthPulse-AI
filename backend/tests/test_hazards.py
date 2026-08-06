"""Tests for the hazard template registry: flood parity, wildfire math, levels,
scope switch to the California wildfire theatre, and hazard-aware endpoints."""

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
        from app.core.models import Location

        if s.query(Location).count() == 0:
            seed_if_empty(s, get_settings())
        yield s
    finally:
        s.close()


def test_registry_has_all_hazards_and_flood_fallback():
    from app.hazards.registry import DEFAULT_HAZARD, HAZARDS, get_hazard

    assert set(HAZARDS) == {
        "flood",
        "wildfire",
        "cyclone",
        "earthquake",
        "tsunami",
        "volcanic",
        "landslide",
        "drought",
        "heatwave",
    }
    assert DEFAULT_HAZARD == "flood"
    assert get_hazard("unknown-id").id == "flood"
    assert get_hazard("wildfire").id == "wildfire"
    assert get_hazard("wildfire").label == "Wildfire"
    assert get_hazard("cyclone").label == "Cyclone"


def test_flood_forecaster_dispatch_is_bit_identical():
    from app.hazards.registry import get_hazard
    from app.ml.forecaster import probability_from_components

    comps = {"rain_intensity": 8.0, "soil_moisture": 6.0, "headroom_deficit": 5.0, "drainage_stress": 6.0}
    direct = get_hazard("flood").probability(comps)
    legacy = probability_from_components(comps)
    assert abs(direct - legacy) < 1e-12


def test_wildfire_probability_monotonic_with_fuel_and_wind():
    from app.hazards.registry import get_hazard

    wf = get_hazard("wildfire")
    calm = wf.probability(
        {"fuel_dryness": 1, "aridity_index": 1, "wind_kick": 1, "thermal_anomaly": 1, "ignition_reports": 0}
    )
    moderate = wf.probability(
        {"fuel_dryness": 6, "aridity_index": 6, "wind_kick": 5, "thermal_anomaly": 5, "ignition_reports": 2}
    )
    extreme = wf.probability(
        {"fuel_dryness": 11, "aridity_index": 10, "wind_kick": 11, "thermal_anomaly": 10, "ignition_reports": 8}
    )
    assert calm < moderate < extreme
    assert 0.0 <= calm <= 1.0 and extreme > 0.8


def test_cyclone_probability_monotonic_and_wind_dominant():
    from app.hazards.registry import get_hazard

    cy = get_hazard("cyclone")
    calm = cy.probability({"storm_wind": 1, "surge_coupling": 1, "rain_burst": 1, "track_pressure": 1})
    building = cy.probability({"storm_wind": 6, "surge_coupling": 5, "rain_burst": 5, "track_pressure": 4})
    severe = cy.probability({"storm_wind": 11, "surge_coupling": 10, "rain_burst": 9, "track_pressure": 8})
    assert calm < building < severe
    # wind field carries the largest marginal weight of any single driver
    base = {"storm_wind": 5, "surge_coupling": 5, "rain_burst": 5, "track_pressure": 5}
    base_p = cy.probability(base)
    wind_marginal = cy.probability({**base, "storm_wind": 6}) - base_p
    surge_marginal = cy.probability({**base, "surge_coupling": 6}) - base_p
    rain_marginal = cy.probability({**base, "rain_burst": 6}) - base_p
    track_marginal = cy.probability({**base, "track_pressure": 6}) - base_p
    assert wind_marginal > surge_marginal > rain_marginal > track_marginal
    assert severe > 0.8


def test_levels_are_hazard_scoped():
    from app.hazards.levels import level_for

    assert level_for("flood", 0.8) == "critical"
    assert level_for("flood", 0.6) == "high"
    assert level_for("flood", 0.4) == "moderate"
    assert level_for("flood", 0.2) == "low"
    # wildfire has a stricter high band (0.6 vs 0.55)
    assert level_for("wildfire", 0.65) == "high"
    assert level_for("wildfire", 0.7) == "high"
    assert level_for("wildfire", 0.85) == "critical"
    assert level_for("wildfire", 0.4) == "moderate"
    assert level_for("wildfire", 0.3) == "low"


def test_wildfire_seed_generates_five_california_zones():
    from app.data.seeds.generate_wildfire import ZONES, generate

    data = generate()
    zones = data["zones"]
    assert len(zones) == len(ZONES) == 5
    assert data["scope"] == "wildfire"
    assert {z["hazard_type"] for z in zones} == {"wildfire"}
    for z in zones:
        assert len(z["weather"]) == 72
        assert len(z["satellite"]) == 36
        # fire weather is dry: humidity collapses, wind ramps
        assert z["weather"][0]["humidity"] > z["weather"][-1]["humidity"]
        assert z["weather"][-1]["wind_kmh"] > z["weather"][0]["wind_kmh"]
        assert z["satellite"][-1]["soil_moisture_anomaly"] < z["satellite"][0]["soil_moisture_anomaly"]
        assert z["citizen"]  # smoke sightings in the second half of the window


def test_scope_switch_to_wildfire_theatre(client, db):
    from app.core.models import Location

    r = client.post("/api/v1/scope", json={"scope": "wildfire"})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "wildfire"
    assert body["zones"] == 5

    zones = db.query(Location).all()
    assert {z.hazard_type for z in zones} == {"wildfire"}
    assert {z.region for z in zones} >= {"Sonoma County", "Mariposa County"}

    # restore chennai so sibling tests stay deterministic
    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_wildfire_live_pipeline_high_risk_at_peak(client, db):
    from app.agents.orchestrator import build_agent_outputs
    from app.core.models import Location
    from app.services.risk_evolution import evolution

    client.post("/api/v1/scope", json={"scope": "wildfire"})
    zone = db.query(Location).filter_by(id="ca_mariposa").first()
    assert zone is not None

    outputs, _ = build_agent_outputs(db, zone.id)
    p = outputs["prediction"]
    assert 0.5 < p["risk_probability"] <= 1.0
    assert p["severity"] >= 2.0

    ev = evolution(db, zone)
    probs = [pt["risk_probability"] for pt in ev["points"]]
    assert min(probs) < 0.4 < max(probs)
    now = next(pt for pt in ev["points"] if pt["is_now"])
    assert now["level"] in {"high", "critical"}

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_wildfire_comparative_analysis_hazard_aware(client, db):
    from app.core.models import Location

    client.post("/api/v1/scope", json={"scope": "wildfire"})
    zone = db.query(Location).filter_by(id="ca_santa_rosa").first()
    r = client.get(f"/api/v1/decisions/compare/{zone.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["hazard"] == "wildfire"
    assert body["live"]["level"] in {"high", "critical"}

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_india_seed_covers_all_states_and_three_hazards():
    from app.data.seeds.generate_india import CAPITALS, UTS, generate

    data = generate()
    zones = data["zones"]
    assert len(zones) == 80
    assert len(CAPITALS) == 29 and len(UTS) == 8
    assert data["scope"] == "india"
    by_hazard = {h: [z for z in zones if z["hazard_type"] == h] for h in ("flood", "cyclone", "wildfire")}
    assert all(len(v) > 0 for v in by_hazard.values())
    # coastal cyclone belt, Himalayan wildfire belt and Ganges floodplain all present
    coastal = {z["region"] for z in by_hazard["cyclone"]}
    assert {"Odisha", "West Bengal", "Andhra Pradesh", "Tamil Nadu", "Kerala"} <= coastal
    assert "Nagaland" in {z["region"] for z in by_hazard["wildfire"]}
    assert {"Bihar", "Assam", "Uttar Pradesh"} <= {z["region"] for z in by_hazard["flood"]}
    # every zone carries canonical telemetry
    for z in zones:
        assert len(z["weather"]) == 72
        assert len(z["satellite"]) == 36
    # cyclone coast carries a storm wind ramp; wildfire hills collapse humidity
    nagapattinam = next(z for z in zones if z["id"] == "in_tn_nagapattinam")
    assert nagapattinam["weather"][-1]["wind_kmh"] > nagapattinam["weather"][0]["wind_kmh"] + 20
    nainital = next(z for z in zones if z["id"] == "in_uk_nain")
    assert nainital["weather"][-1]["humidity"] < nainital["weather"][0]["humidity"] - 15
    # Ganges basin floods harder than plateau capitals
    darbhanga = next(z for z in zones if z["id"] == "in_br_darb")
    hyderabad = next(z for z in zones if z["id"] == "in_tg_hyd")
    assert max(w["rainfall_mm"] for w in darbhanga["weather"]) > max(w["rainfall_mm"] for w in hyderabad["weather"])


def test_scope_switch_to_india_theatre(client, db):
    from app.core.models import Location

    r = client.post("/api/v1/scope", json={"scope": "india"})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "india"
    assert body["zones"] == 80

    zones = db.query(Location).all()
    assert {z.hazard_type for z in zones} == {"flood", "cyclone", "wildfire"}
    assert {z.region for z in zones} >= {"Bihar", "Nagaland", "Lakshadweep", "Delhi"}

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_cyclone_live_pipeline_surge_driven(client, db):
    from app.agents.orchestrator import build_agent_outputs
    from app.core.models import Location
    from app.services.risk_evolution import evolution

    client.post("/api/v1/scope", json={"scope": "india"})
    zone = db.query(Location).filter_by(id="in_tn_nagapattinam").first()
    assert zone is not None and zone.hazard_type == "cyclone"

    outputs, _ = build_agent_outputs(db, zone.id)
    comps = outputs["risk_fusion"]["components"]
    assert {"storm_wind", "surge_coupling", "rain_burst", "track_pressure"} == set(comps)
    p = outputs["prediction"]
    assert 0.5 < p["risk_probability"] <= 1.0

    ev = evolution(db, zone)
    probs = [pt["risk_probability"] for pt in ev["points"]]
    assert min(probs) < 0.4 < max(probs)
    now = next(pt for pt in ev["points"] if pt["is_now"])
    assert now["level"] in {"high", "critical"}

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_cyclone_comparative_analysis_hazard_aware(client, db):
    from app.core.models import Location

    client.post("/api/v1/scope", json={"scope": "india"})
    zone = db.query(Location).filter_by(id="in_wb_s24").first()
    r = client.get(f"/api/v1/decisions/compare/{zone.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["hazard"] == "cyclone"
    assert body["live"]["level"] in {"high", "critical"}
    assert body["analogues"][0]["event"]  # hazard-scoped analogue from the cyclone memory band

    client.post("/api/v1/scope", json={"scope": "chennai"})


NEW_HAZARDS = ["earthquake", "tsunami", "volcanic", "landslide", "drought", "heatwave"]


def test_new_hazard_templates_complete():
    from app.hazards.registry import get_hazard

    for hid in NEW_HAZARDS:
        h = get_hazard(hid)
        assert h.fusion is not None and h.history is not None and h.formula is not None
        assert h.hourly is not None and h.causal is not None and h.recommend is not None
        assert h.features and h.evidence and h.interventions
        assert h.scale > 0
        for f in h.features:
            comps = {k: 0.0 for k in h.features}
            comps[f] = 12.0
            assert h.formula(comps) > h.formula({k: 0.0 for k in h.features}), f"{hid}:{f}"


def test_new_hazard_memory_bands():
    from app.services.environmental_memory import analogue_matches, memory_for

    for hid in NEW_HAZARDS:
        mem = memory_for("mem_asia_probe", hid)
        assert mem.hazard == hid and len(mem.events) >= 2
        matches = analogue_matches("mem_asia_probe", {k: 9.0 for k in mem.events[0].signature}, hid)
        assert matches and matches[0]["event"]


def test_earthquake_pipeline_with_seismic_telemetry(client, db):
    from datetime import datetime, timedelta

    from app.agents.orchestrator import build_agent_outputs
    from app.core import models

    client.post("/api/v1/scope", json={"scope": "chennai"})
    zone = db.query(models.Location).filter_by(id="adyar_1").first()
    assert zone is not None
    zone.hazard_type = "earthquake"
    db.commit()

    base = datetime.fromisoformat("2026-01-01T00:00:00")
    for i, (metric, value) in enumerate(
        [
            ("ground_accel", 0.8),
            ("seismic_energy", 140.0),
            ("ground_accel", 0.7),
            ("seismic_energy", 110.0),
            ("ground_accel", 0.5),
        ]
    ):
        db.add(
            models.IngestedDatum(
                location_id=zone.id,
                captured_at=base + timedelta(hours=i),
                source_id="usgs-seismic",
                metric=metric,
                value=value,
                unit="g" if "accel" in metric else "GJ",
            )
        )
    db.commit()

    outputs, _ = build_agent_outputs(db, zone.id)
    comps = outputs["risk_fusion"]["components"]
    assert {"ground_accel", "energy_release", "building_vulnerability", "shaking_reports"} == set(comps)
    assert comps["ground_accel"] > 3.0  # live accel rows drive the component
    p = outputs["prediction"]["risk_probability"]
    assert 0.3 < p < 1.0

    db.query(models.IngestedDatum).delete()
    db.commit()
    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_scope_switch_to_asia_theatre(client, db):
    from app.core.models import Location

    r = client.post("/api/v1/scope", json={"scope": "asia"})
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "asia"
    assert body["zones"] == 107

    zones = db.query(Location).all()
    assert {z.hazard_type for z in zones} == {
        "flood",
        "cyclone",
        "wildfire",
        "earthquake",
        "tsunami",
        "volcanic",
        "landslide",
        "drought",
        "heatwave",
    }
    assert {z.region for z in zones} >= {"Japan", "Indonesia", "Iraq", "Mongolia"}

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_asia_seismic_zones_carry_ingested_telemetry(client, db):
    from app.core import models

    client.post("/api/v1/scope", json={"scope": "asia"})
    zone = db.query(models.Location).filter_by(id="as_jp_tok").first()
    assert zone is not None and zone.hazard_type == "earthquake"

    rows = db.query(models.IngestedDatum).filter_by(location_id="as_jp_tok").all()
    metrics = {r.metric for r in rows}
    assert {"ground_accel", "seismic_energy"} <= metrics
    assert max(r.value for r in rows if r.metric == "ground_accel") > 0.5  # mainshock present
    assert max(r.value for r in rows if r.metric == "seismic_energy") > 50

    volcano = db.query(models.Location).filter_by(id="as_id_jog").first()
    assert volcano is not None
    volc_metrics = {r.metric for r in db.query(models.IngestedDatum).filter_by(location_id="as_id_jog").all()}
    assert {"volcanic_tremor", "so2_flux", "ash_plume_km"} <= volc_metrics

    client.post("/api/v1/scope", json={"scope": "chennai"})


def test_asia_live_pipeline_per_hazard(client, db):
    from app.agents.orchestrator import build_agent_outputs
    from app.core import models

    client.post("/api/v1/scope", json={"scope": "asia"})
    probes = {
        "as_jp_tok": {"ground_accel", "energy_release", "building_vulnerability", "shaking_reports"},
        "as_lk_cmb": {"sea_disturbance", "source_energy", "coastal_exposure", "sea_state_report"},
        "as_id_jog": {"tremor_amplitude", "so2_flux", "ash_plume", "ashfall_report"},
        "as_np_pkr": {"slope_saturation", "rain_trigger", "terrain_fragility", "slippage_report"},
        "as_ir_krm": {"precipitation_deficit", "soil_desiccation", "heat_stress", "water_scarcity"},
        "as_iq_bgd": {"thermal_excess", "dry_bulb_load", "stagnation", "heat_illness"},
    }
    for zid, expected in probes.items():
        zone = db.query(models.Location).filter_by(id=zid).first()
        assert zone is not None, zid
        outputs, _ = build_agent_outputs(db, zid)
        comps = outputs["risk_fusion"]["components"]
        assert expected == set(comps), zid
        p = outputs["prediction"]["risk_probability"]
        assert 0.0 <= p <= 1.0, zid
        assert outputs["prediction"]["severity"] > 0, zid

    client.post("/api/v1/scope", json={"scope": "chennai"})
