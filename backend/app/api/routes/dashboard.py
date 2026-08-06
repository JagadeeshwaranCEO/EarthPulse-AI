"""Dashboard, pulse, locations, sim clock."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.config import get_settings
from app.core.db import get_db
from app.core.models import Alert, Location, PulseScore
from app.core.security import require_api_key
from app.ml.pulse import compute_pulse
from app.schemas import Dashboard, PulseView
from app.services.ticker import get_state, set_hour

log = logging.getLogger("earthpulse")

router = APIRouter(tags=["dashboard"])


def live_risk_summaries(db: Session) -> list[dict]:
    """Risk summaries computed live from the pipeline — follows the sim clock."""
    from app.hazards.levels import level_for
    from app.services.verification import zone_precision

    rows = []
    for loc in db.query(Location).all():
        outputs, _ = build_agent_outputs(db, loc.id)
        pred = outputs.get("prediction") or {}
        if not pred:
            continue
        trend = (
            "rising"
            if pred.get("forecast_series") and pred["forecast_series"].mean[-1] > pred.get("risk_probability", 0) * 1.05
            else "steady"
        )
        try:
            precision = zone_precision(db, loc)
        except Exception:
            log.warning("zone_precision failed for %s — precision_tier omitted", loc.id, exc_info=True)
            precision = {}
        rows.append(
            {
                "location_id": loc.id,
                "location_name": loc.name,
                "region": loc.region,
                "lat": loc.lat,
                "lon": loc.lon,
                "event_type": loc.hazard_type,
                "level": level_for(loc.hazard_type, pred.get("risk_probability", 0)),
                "risk_probability": pred.get("risk_probability", 0),
                "severity": pred.get("severity", 0),
                "confidence": pred.get("confidence", 0),
                "trend": trend,
                "horizon_h": pred.get("horizon_h", 24),
                "precision_tier": precision.get("tier"),
                "updated_at": datetime.now(timezone.utc),
            }
        )
    return sorted(rows, key=lambda r: -r["risk_probability"])


@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(db: Session = Depends(get_db)):
    loc = db.query(Location).first()
    if loc is None:
        raise HTTPException(503, "no seed data; run backend with seed_on_boot=true")

    outputs, _ = build_agent_outputs(db, loc.id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    anomaly = outputs.get("risk_fusion", {}).get("anomaly_score", 0.0)
    alerts = db.query(Alert).filter_by(resolved=False).all()
    pulse = compute_pulse(components, anomaly, len(alerts))

    db.add(PulseScore(location_id=loc.id, score=pulse.score, factors=pulse.factors))
    db.commit()

    top_risks = live_risk_summaries(db)
    return Dashboard(
        pulse=PulseView(
            location_id=loc.id,
            score=pulse.score,
            factors=pulse.factors,
            recorded_at=datetime.now(timezone.utc),
            band=pulse.band,
        ),
        alerts=[
            {
                "id": a.id,
                "location_id": a.location_id,
                "level": a.level,
                "title": a.title,
                "summary": a.summary,
                "raised_at": a.raised_at,
            }
            for a in alerts
        ],
        risks=top_risks,
        crisis=any(r["level"] == "critical" for r in top_risks),
        time=datetime.now(timezone.utc),
        tick_seconds=3.0,
        scope=get_settings().scope,
    )


@router.get("/dashboard/pulse", response_model=PulseView)
def get_pulse(location_id: str | None = None, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id) if location_id else db.query(Location).first()
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, loc.id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    anomaly = outputs.get("risk_fusion", {}).get("anomaly_score", 0.0)
    alerts = db.query(Alert).filter_by(location_id=loc.id, resolved=False).count()
    pulse = compute_pulse(components, anomaly, alerts)
    return PulseView(
        location_id=loc.id,
        score=pulse.score,
        factors=pulse.factors,
        recorded_at=datetime.now(timezone.utc),
        band=pulse.band,
    )


@router.get("/sim/clock")
def get_clock():
    return get_state()


@router.post("/sim/clock", dependencies=[require_api_key])
def set_clock(hour: float):
    state = get_state()
    return {"hour": set_hour(hour), "max": state["max"], "step": state["step"]}
