"""Decision Intelligence routes — optimize, memory, evolution, brief, scientist XAI."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.api.routes.dashboard import live_risk_summaries
from app.core.db import get_db
from app.core.models import Location
from app.core.security import require_api_key
from app.services.comparative_analysis import comparative_analysis
from app.services.decision_optimizer import (
    DecisionOptimizer,
    ResourceInventory,
    ZoneRisk,
    build_execution_timeline,
)
from app.services.environmental_memory import memory_view
from app.services.mission_brief import build_mission_brief
from app.services.risk_evolution import evolution as risk_evolution
from app.services.trust_score import compute_trust

log = logging.getLogger("earthpulse")

router = APIRouter(prefix="/decisions", tags=["decisions"])

DEFAULT_INVENTORY = {"boats": 12, "pumps": 8, "shelters": 5, "budget_inr_crores": 15.0, "personnel": 40}


def _peak_hour(db: Session, location_id: str | None = None) -> float:
    """Forecast peak hour for the timeline — from the evolution engine."""
    loc = db.get(Location, location_id) if location_id else db.query(Location).first()
    if loc is None:
        return 66.0
    try:
        return float(risk_evolution(db, loc, lookback_h=6, horizon_h=24)["peak_at_hour"])
    except Exception:
        log.warning("peak-hour evolution failed for %s — defaulting to 66.0", loc.id, exc_info=True)
        return 66.0


def _zone_risks(db: Session) -> list[ZoneRisk]:
    """Live risk state → optimizer input (probability, severity, population)."""
    rows = live_risk_summaries(db)
    pops = {loc.id: loc.population for loc in db.query(Location).all()}
    return [
        ZoneRisk(
            location_id=r["location_id"],
            name=r["location_name"],
            risk_probability=r["risk_probability"],
            severity=r["severity"],
            population=pops.get(r["location_id"], 100_000),
            lat=r["lat"],
            lon=r["lon"],
        )
        for r in rows
    ]


@router.post("/optimize", dependencies=[require_api_key])
def optimize(inventory: dict | None = None, db: Session = Depends(get_db)):
    """Constrained multi-objective resource allocation across all live zones."""
    inv = {**DEFAULT_INVENTORY, **(inventory or {})}
    inv_obj = ResourceInventory(**{k: inv.get(k) for k in ResourceInventory.__dataclass_fields__})
    optimizer = DecisionOptimizer()
    zone_risks = _zone_risks(db)
    strategies = optimizer.optimize(zone_risks, inv_obj)
    analysis = optimizer.robustness_analysis(zone_risks, inv_obj, strategies)
    peak = _peak_hour(db)
    for s in strategies:
        if s.is_recommended:
            s.execution_timeline = build_execution_timeline(peak)
    return {
        "inventory": inv,
        "analysis": analysis,
        "peak_hour": peak,
        "strategies": [{**s.__dict__, "allocations": s.allocations} for s in strategies],
    }


@router.get("/memory/{location_id}")
def memory(location_id: str, db: Session = Depends(get_db)):
    """Environmental Memory — historical analogues for current telemetry."""
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, location_id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    view = memory_view(location_id, components, loc.hazard_type)
    view["location_name"] = loc.name
    view["components_now"] = {k: round(v, 3) for k, v in components.items()}
    view["provenance"] = {
        "historical_events": "Chennai flood records 2015/2021/2023 (synthetic signature store)",
        "is_synthetic": True,
    }
    return view


@router.get("/evolution/{location_id}")
def evolution(location_id: str, lookback_h: int = 48, horizon_h: int = 24, db: Session = Depends(get_db)):
    """Hour-by-hour risk evolution for a location across the sim window."""
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    return risk_evolution(db, loc, lookback_h=lookback_h, horizon_h=horizon_h)


@router.post("/brief", dependencies=[require_api_key])
def mission_brief(inventory: dict | None = None, db: Session = Depends(get_db)):
    """Stakeholder mission brief from the recommended strategy."""
    inv = {**DEFAULT_INVENTORY, **(inventory or {})}
    inv_obj = ResourceInventory(**{k: inv.get(k) for k in ResourceInventory.__dataclass_fields__})
    optimizer = DecisionOptimizer()
    zone_risks = _zone_risks(db)
    strategies = optimizer.optimize(zone_risks, inv_obj)
    recommended = next((s for s in strategies if s.is_recommended), strategies[0])
    analysis = optimizer.robustness_analysis(zone_risks, inv_obj, strategies)

    loc = db.get(Location, db.query(Location).first().id)
    outputs, _ = build_agent_outputs(db, loc.id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    mem = memory_view(loc.id, components, loc.hazard_type)
    ev = risk_evolution(db, loc, lookback_h=24, horizon_h=24)
    recommended.execution_timeline = build_execution_timeline(ev["peak_at_hour"])
    trust = compute_trust(db, loc.id)

    top_risks = live_risk_summaries(db)
    return build_mission_brief(
        strategy=recommended,
        top_risks=top_risks,
        analysis=analysis,
        peak_risk=ev["peak_probability"],
        peak_at_hour=ev["peak_at_hour"],
        now_hour=ev["now_hour"],
        memory_line=mem["headline"],
        trust=trust,
    )


@router.get("/compare/{location_id}")
def compare(location_id: str, db: Session = Depends(get_db)):
    """Comparative live analysis — current telemetry vs the historical record."""
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "location not found")
    try:
        return comparative_analysis(db, location_id)
    except Exception as exc:
        log.warning("comparative analysis failed for %s", location_id, exc_info=True)
        raise HTTPException(422, f"comparative analysis failed: {exc}") from None


@router.get("/trust/{location_id}")
def trust(location_id: str, db: Session = Depends(get_db)):
    """Data trust decomposition — sensors, freshness, integrity, analogue, model."""
    if db.get(Location, location_id) is None:
        raise HTTPException(404, "location not found")
    return compute_trust(db, location_id)


@router.get("/scientist/{location_id}")
def scientist(location_id: str, db: Session = Depends(get_db)):
    """Explain Like a Scientist — the full XAI breakdown of one score."""
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, location_id)
    comps = outputs.get("risk_fusion", {}).get("components", {})
    pred = outputs.get("prediction", {})
    chain = outputs.get("explanation", {}).get("causal_chain", {"nodes": [], "edges": []})
    attribution = outputs.get("explanation", {}).get("attribution", [])

    signal = (
        1.0 * comps.get("rain_intensity", 0)
        + 0.8 * comps.get("soil_moisture", 0)
        + 1.2 * comps.get("headroom_deficit", 0)
        + 0.7 * comps.get("drainage_stress", 0)
        + 0.3 * comps.get("citizen_pressure", 0)
    )
    weights = {
        "rain_intensity": 1.0,
        "soil_moisture": 0.8,
        "headroom_deficit": 1.2,
        "drainage_stress": 0.7,
        "citizen_pressure": 0.3,
    }
    steps = [
        {
            "equation": f"signal = 1.0·rain({comps.get('rain_intensity', 0):.2f}) + 0.8·soil({comps.get('soil_moisture', 0):.2f}) "
            f"+ 1.2·headroom({comps.get('headroom_deficit', 0):.2f}) + 0.7·stress({comps.get('drainage_stress', 0):.2f}) "
            f"+ 0.3·citizen({comps.get('citizen_pressure', 0):.2f}) = {signal:.2f}",
            "explanation": "Weighted causal sum of the fused components; headroom binds hardest (1.2).",
        },
        {
            "equation": f"P = 1/(1+e^−(({signal:.2f}−26)/8.67)) = {pred.get('risk_probability', 0):.3f}",
            "explanation": "Logistic squash with scale 52 (calibrated on the Chennai storm profile). "
            "P≥0.75 → critical, 0.55–0.75 high, 0.3–0.55 moderate.",
        },
        {
            "equation": f"severity = P·5 = {pred.get('severity', 0):.1f}/5; "
            f"confidence = 0.85·freshness − 2·residual_std = {pred.get('confidence', 0):.2f}",
            "explanation": "Severity scales linearly with probability; confidence penalizes "
            "forecast residual dispersion and stale data.",
        },
    ]
    top = sorted(attribution, key=lambda a: -a["influence"])[:3]
    return {
        "location_id": location_id,
        "score": pred.get("risk_probability", 0),
        "model_name": pred.get("model_name", "earthpulse-stream-v1"),
        "formula_steps": steps,
        "dominant_factors": [
            {
                "feature": a["feature"],
                "influence": round(a["influence"], 3),
                "weight": weights.get(a["feature"], 0.0),
                "description": a["description"],
            }
            for a in top
        ],
        "causal_chain": {"nodes": chain.get("nodes", []), "edges": chain.get("edges", [])},
        "uncertainty": pred.get("bounds", {}),
        "limitations": pred.get("limitations", []),
        "provenance_note": "All signals synthetic demo data; instrumentation sources cited per evidence item.",
    }
