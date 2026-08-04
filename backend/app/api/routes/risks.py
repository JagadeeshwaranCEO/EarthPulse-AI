"""Risks: summaries, detail, prediction, causal chain, attribution, evidence, recommendations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.api.routes.dashboard import live_risk_summaries
from app.core.db import get_db
from app.core.models import EvidenceObject, Location, Prediction, Source
from app.ml.attribution import compute_attribution
from app.schemas import CausalChain, Evidence, RiskDetail, RiskSummary
from app.services.evidence import to_schema
from app.services.llm import llm_mode

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get("", response_model=list[RiskSummary])
def list_risks(db: Session = Depends(get_db)):
    return live_risk_summaries(db)


@router.get("/{location_id}", response_model=RiskDetail)
def get_risk(location_id: str, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    summary = next((r for r in live_risk_summaries(db) if r["location_id"] == location_id), None)
    if summary is None:
        raise HTTPException(404, "no risk state for location yet — run pipeline first")

    outputs, _ = build_agent_outputs(db, location_id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    chain = outputs.get("explanation", {}).get("causal_chain", {"nodes": [], "edges": []})
    attribution = compute_attribution(components)
    pred_out = outputs.get("prediction") or {}

    from app.services.crossing import project_crossing
    from app.services.verification import zone_precision

    precision = zone_precision(db, loc)
    try:
        crossing = project_crossing(db, loc)
    except Exception:
        crossing = None

    pred = (
        db.query(Prediction)
        .filter_by(location_id=location_id, event_type=loc.hazard_type)
        .order_by(desc(Prediction.generated_at))
        .first()
    )
    evidence_objs = db.query(EvidenceObject).filter_by(prediction_id=pred.id).all() if pred else []
    sources = {s.id: s for s in db.query(Source).all()}
    evidence = [to_schema(e, sources[e.source_id]) for e in evidence_objs if e.source_id in sources]

    return RiskDetail(
        location_id=loc.id, location_name=loc.name, lat=loc.lat, lon=loc.lon,
        event_type=loc.hazard_type, level=summary["level"],
        risk_probability=summary["risk_probability"], severity=summary["severity"],
        confidence=summary["confidence"],
        trend=summary["trend"],
        horizon_h=summary["horizon_h"], updated_at=summary["updated_at"],
        precision_tier=precision.get("tier"),
        precision={
            "tier": precision.get("tier"),
            "brier": precision.get("brier"),
            "brier_skill": precision.get("brier_skill"),
            "auc": precision.get("auc"),
            "climatology": precision.get("climatology"),
            "calibration": precision.get("calibration"),
            "band_tightness": precision.get("band_tightness"),
            "verified_samples": precision.get("samples"),
            "method": "rolling holdout verification vs realized telemetry",
        },
        crossing=crossing,
        components={k: round(v, 3) for k, v in components.items()},
        attribution=[
            {"feature": a.feature, "influence": a.influence, "direction": a.direction, "description": a.description}
            for a in attribution
        ],
        causal_chain=CausalChain(nodes=chain.get("nodes", []), edges=chain.get("edges", [])),
        evidence=evidence,
        limitations=pred_out.get("limitations") or (pred.limitations if pred else []),
        model_name=pred_out.get("model_name") or (pred.model_name if pred else ""),
        llm_mode=llm_mode(),
    )


@router.get("/{location_id}/prediction")
def get_prediction(location_id: str, horizon: int = 24, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, location_id)
    pred = outputs.get("prediction") or {}
    fc = pred.get("forecast_series")
    if fc is None:
        raise HTTPException(404, "no prediction state")
    band = [up - lo for up, lo in zip(fc.upper, fc.lower)]
    return {
        "location_id": location_id,
        "model_name": pred.get("model_name", "earthpulse-stream-v1"),
        "generated_at": datetime.now(timezone.utc),
        "horizon_h": fc.horizon_h,
        "probability_now": pred.get("risk_probability", 0),
        "peak_probability": pred.get("peak_probability", 0),
        "peak_in_h": pred.get("peak_in_h", 0),
        "lead_ladder": pred.get("lead_ladder", []),
        "bounds": pred.get("bounds", {}),
        "residual_std": round(fc.residual_std, 4),
        "sharpness": round(float(sum(band) / len(band)) if band else 0.0, 4),
        "outlook": pred.get("outlook", []),
        "points": [
            {"t": t.isoformat(), "mean": round(m, 3), "lower": round(lo, 3), "upper": round(up, 3)}
            for t, m, lo, up in zip(fc.series_t, fc.mean, fc.lower, fc.upper)
        ],
    }


@router.get("/{location_id}/causal-chain")
def get_causal_chain(location_id: str, db: Session = Depends(get_db)):
    outputs, _ = build_agent_outputs(db, location_id)
    return outputs.get("explanation", {}).get("causal_chain", {"nodes": [], "edges": []})


@router.get("/{location_id}/attribution")
def get_attribution(location_id: str, db: Session = Depends(get_db)):
    outputs, _ = build_agent_outputs(db, location_id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    items = compute_attribution(components)
    return [{"feature": i.feature, "influence": i.influence, "direction": i.direction, "description": i.description} for i in items]


@router.get("/{location_id}/evidence", response_model=list[Evidence])
def get_evidence(location_id: str, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    pred = (
        db.query(Prediction)
        .filter_by(location_id=location_id, event_type=loc.hazard_type)
        .order_by(desc(Prediction.generated_at))
        .first()
    )
    if pred is None:
        return []
    sources = {s.id: s for s in db.query(Source).all()}
    return [to_schema(e, sources[e.source_id]) for e in db.query(EvidenceObject).filter_by(prediction_id=pred.id).all() if e.source_id in sources]


@router.get("/{location_id}/recommendations")
def get_recommendations(location_id: str, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, location_id)
    pred = (
        db.query(Prediction)
        .filter_by(location_id=location_id, event_type=loc.hazard_type)
        .order_by(desc(Prediction.generated_at))
        .first()
    )
    recs = outputs.get("recommendation", {}).get("recommendations", [])
    evidence_ids = pred.evidence_ids if pred else []
    for r in recs:
        r["evidence_ids"] = evidence_ids
    return recs
