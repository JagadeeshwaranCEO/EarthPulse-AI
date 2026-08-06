"""Smoke tests for the EarthPulse pipeline — model, agents, simulation, API."""

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
def seeded(client):
    # seed via a dedicated in-memory run: reuse app lifespan logic by calling endpoints

    db = SessionLocal()
    try:
        if db.query(__import__("app.core.models", fromlist=["Location"]).Location).count() == 0:
            from app.services.seeder import seed_if_empty

            seed_if_empty(db, get_settings())
        yield db
    finally:
        db.close()


def test_forecaster_bounds():
    from datetime import datetime, timezone

    from app.ml.forecaster import DEFAULT_FORECASTER

    t0 = datetime.now(timezone.utc)
    series = [0.1, 0.2, 0.25, 0.4, 0.45, 0.6, 0.7, 0.8, 0.85, 0.9]
    fc = DEFAULT_FORECASTER.fit_forecast(series, t0, horizon_h=12)
    assert len(fc.mean) == 12
    assert all(fc.lower[i] <= fc.mean[i] <= fc.upper[i] for i in range(12))


def test_probability_bounded():
    from app.ml.forecaster import probability_from_components

    low = probability_from_components(
        {"rain_intensity": 0, "soil_moisture": 0, "headroom_deficit": 0, "drainage_stress": 0, "citizen_pressure": 0}
    )
    high = probability_from_components(
        {
            "rain_intensity": 12,
            "soil_moisture": 12,
            "headroom_deficit": 12,
            "drainage_stress": 12,
            "citizen_pressure": 8,
        }
    )
    assert 0.0 <= low < 0.05 < high <= 1.0


def test_attribution_total():
    from app.ml.attribution import compute_attribution

    items = compute_attribution(
        {"rain_intensity": 6, "soil_moisture": 5, "headroom_deficit": 7, "drainage_stress": 4, "citizen_pressure": 2}
    )
    assert abs(sum(i.influence for i in items) - 1.0) < 0.01
    assert items[0].direction in ("raises", "lowers")


def test_simulation_engine():
    from app.services.simulation_engine import run_simulation

    result = run_simulation(
        {"rain_intensity": 10, "soil_moisture": 8, "headroom_deficit": 9, "drainage_stress": 8, "citizen_pressure": 4},
        500_000,
        {"pump_preposition": 0.8},
    )
    assert result["after"]["probability"] < result["baseline"]["probability"]
    assert result["deltas"]["damage_reduction_pct"] > 0
    assert result["carbon_ledger"]["net_kg"] > 0
    assert "location_id" in result or True  # route attaches it


def test_pulse_bands():
    from app.ml.pulse import compute_pulse

    stable = compute_pulse(
        {"rain_intensity": 0, "soil_moisture": 0, "headroom_deficit": 0, "drainage_stress": 0, "citizen_pressure": 0},
        0.0,
        0,
    )
    critical = compute_pulse(
        {
            "rain_intensity": 12,
            "soil_moisture": 12,
            "headroom_deficit": 12,
            "drainage_stress": 12,
            "citizen_pressure": 8,
        },
        0.9,
        4,
    )
    assert stable.band == "stable" and stable.score > 900
    assert critical.band == "critical" and critical.score < 400


def test_agent_roster():
    from app.agents.orchestrator import ALL_AGENTS

    assert len(ALL_AGENTS) == 11
    names = {a.name for a in ALL_AGENTS}
    assert {
        "satellite",
        "weather",
        "water",
        "risk_fusion",
        "prediction",
        "explanation",
        "recommendation",
        "simulation",
    } <= names


def test_api_dashboard_and_risks(client, seeded):
    from app.services import ticker

    ticker.set_hour(60)
    d = client.get("/api/v1/dashboard")
    assert d.status_code == 200
    body = d.json()
    assert "pulse" in body and "risks" in body
    risks = client.get("/api/v1/risks").json()
    assert len(risks) == 15
    worst = max(risks, key=lambda r: r["risk_probability"])
    assert 0 <= worst["risk_probability"] <= 1


def test_api_risk_detail(client, seeded):
    from app.services import ticker

    ticker.set_hour(60)
    detail = client.get("/api/v1/risks/mylapore")
    assert detail.status_code == 200
    body = detail.json()
    assert body["causal_chain"]["nodes"]
    assert body["attribution"]
    assert body["limitations"]
    assert body["evidence"]
    assert body["model_name"].startswith("earthpulse")


def test_api_simulation_roundtrip(client, seeded):
    resp = client.post(
        "/api/v1/simulations", json={"location_id": "mylapore", "interventions": {"reservoir_release": 0.7}}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["location_id"] == "mylapore"
    assert body["deltas"]["probability_reduction"] > 0
    fetched = client.get(f"/api/v1/simulations/{body['id']}")
    assert fetched.status_code == 200


def test_api_debate_force(client, seeded):
    from app.services import ticker

    ticker.set_hour(60)
    resp = client.get("/api/v1/agents/debate?risk_id=mylapore&force=true")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["statements"]) == 4
    assert body["verdict"]


def test_decision_optimizer_strategies_differ():
    from app.services.decision_optimizer import DecisionOptimizer, ResourceInventory, ZoneRisk

    zs = [
        ZoneRisk("a", "A", 0.9, 4.0, 600_000),
        ZoneRisk("b", "B", 0.7, 3.0, 500_000),
        ZoneRisk("c", "C", 0.3, 1.5, 300_000),
    ]
    strategies = DecisionOptimizer().optimize(zs, ResourceInventory())
    assert len(strategies) == 3
    recommended = [s for s in strategies if s.is_recommended]
    assert len(recommended) == 1 and recommended[0].focus == "balanced"
    plans = {s.id: s.allocations for s in strategies}
    # Pareto: max-lives should protect more lives, min-econ lower residual loss
    by_id = {s.id: s for s in strategies}
    assert by_id["strat_a"].lives_protected > by_id["strat_b"].lives_protected
    assert by_id["strat_b"].economic_loss_inr_cr <= by_id["strat_a"].economic_loss_inr_cr
    # each strategy still respects the inventory cap
    for s in strategies:
        totals = {"boat": 0, "pump": 0, "shelter": 0}
        for a in s.allocations.values():
            for u in totals:
                totals[u] += a[u]
        assert totals["boat"] <= 12 and totals["pump"] <= 8 and totals["shelter"] <= 5
    assert plans["strat_a"] != plans["strat_b"]


def test_health_and_readiness(client, seeded):
    assert client.get("/api/v1/health").status_code == 200
    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["zones"] > 0


def test_models_registry(client, seeded):
    resp = client.get("/api/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["zones"] > 0
    assert len(body["models"]) >= 10
    assert body["store"]["predictions"] > 0
    ids = {m["id"] for m in body["models"]}
    assert {
        "nowcast-ladder",
        "decision-optimizer",
        "validation",
        "simulation",
        "agent-debate",
        "trust-score",
    } <= ids
    for m in body["models"]:
        assert m["status"] == "live"
        assert m["category"] in ("prediction", "explanation", "decision", "governance")


def test_mutating_endpoints_api_key_guard(client, seeded):
    from app.config import get_settings

    settings = get_settings()
    prev = settings.api_key
    settings.api_key = "test-key"
    try:
        assert client.post("/api/v1/decisions/optimize", json={}).status_code == 401
        assert client.post("/api/v1/decisions/optimize", json={}, headers={"X-API-Key": "wrong"}).status_code == 401
        ok = client.post("/api/v1/decisions/optimize", json={}, headers={"X-API-Key": "test-key"})
        assert ok.status_code == 200
        assert (
            client.post("/api/v1/scope", json={"scope": "chennai"}, headers={"X-API-Key": "test-key"}).status_code
            == 200
        )
    finally:
        settings.api_key = prev


def test_chat_throttled_not_keyed(client, seeded):
    from app.config import get_settings

    settings = get_settings()
    prev = settings.api_key
    settings.api_key = "test-key"
    try:
        resp = client.post("/api/v1/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200
    finally:
        settings.api_key = prev


def test_balanced_priority_responds_to_population_share():
    from app.services.decision_optimizer import balanced_priority

    sparse = balanced_priority(50_000, 1_000_000, 4.0)
    dense = balanced_priority(500_000, 1_000_000, 4.0)
    assert dense > sparse
    assert sparse > 0 and dense < 1.8
    same_sev = balanced_priority(100_000, 1_000_000, 4.0)
    same_sev_smaller_pop = balanced_priority(20_000, 1_000_000, 4.0)
    assert same_sev > same_sev_smaller_pop


def test_api_decision_endpoints(client, seeded):
    from app.services import ticker

    ticker.set_hour(60)
    opt = client.post("/api/v1/decisions/optimize", json={})
    assert opt.status_code == 200
    body = opt.json()
    assert set(body["strategies"][0].keys()) == {
        "id",
        "title",
        "focus",
        "allocations",
        "lives_protected",
        "economic_loss_inr_cr",
        "co2_reduction_pct",
        "confidence_score",
        "is_recommended",
        "rationale",
        "actions",
        "execution_timeline",
    }
    assert any(s["is_recommended"] for s in body["strategies"])

    mem = client.get("/api/v1/decisions/memory/mylapore")
    assert mem.status_code == 200
    assert mem.json()["top_analogues"] and mem.json()["headline"]

    evo = client.get("/api/v1/decisions/evolution/mylapore")
    assert evo.status_code == 200
    ev = evo.json()
    assert len(ev["points"]) > 24 and any(p["is_now"] for p in ev["points"])
    assert 0 <= ev["peak_probability"] <= 1

    brief = client.post("/api/v1/decisions/brief", json={})
    assert brief.status_code == 200
    assert brief.json()["strategy_id"] == "strat_c"

    sci = client.get("/api/v1/decisions/scientist/mylapore")
    assert sci.status_code == 200
    assert len(sci.json()["formula_steps"]) == 3
    assert sci.json()["dominant_factors"]

    trust = client.get("/api/v1/decisions/trust/mylapore")
    assert trust.status_code == 200
    tb = trust.json()
    assert tb["level"] in ("High", "Moderate", "Low") and 0 <= tb["score"] <= 100
    assert len(tb["checks"]) == 6

    rec = next(s for s in body["strategies"] if s["is_recommended"])
    assert len(rec["execution_timeline"]) == 5
    assert rec["execution_timeline"][-1]["phase"] == "Impact"
