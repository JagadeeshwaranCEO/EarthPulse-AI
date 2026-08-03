"""Pipeline refresh — run the full agent pipeline per location and persist.

Used at boot and by the live scope-switch endpoint so both theatres produce
persisted predictions + evidence with identical semantics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.core import models
from app.services import evidence as ev_svc


def refresh_predictions(db: Session) -> int:
    """Persist a fresh prediction + evidence + alert per location. Returns zone count."""
    from app.hazards.registry import get_hazard

    count = 0
    for loc in db.query(models.Location).all():
        hazard = get_hazard(loc.hazard_type)
        outputs, _ = build_agent_outputs(db, loc.id)
        comps = outputs.get("risk_fusion", {}).get("components", {})
        pred_out = outputs.get("prediction", {})
        if not pred_out:
            continue
        fc = pred_out.get("forecast_series")
        now = datetime.now(timezone.utc)
        pred = models.Prediction(
            location_id=loc.id,
            event_type=loc.hazard_type,
            generated_at=now,
            horizon_h=fc.horizon_h if fc else 24,
            risk_probability=pred_out.get("risk_probability", 0.0),
            severity=pred_out.get("severity", 0.0),
            confidence=pred_out.get("confidence", 0.0),
            lower_bound=pred_out.get("bounds", {}).get("lower", 0.0),
            upper_bound=pred_out.get("bounds", {}).get("upper", 1.0),
            features=comps,
            attribution=outputs.get("explanation", {}).get("attribution", []),
            limitations=outputs.get("explanation", {}).get("limitations", []),
            model_name=pred_out.get("model_name", "earthpulse-stream-v1"),
            series={
                "t": [t.isoformat() for t in fc.series_t],
                "mean": fc.mean, "lower": fc.lower, "upper": fc.upper,
                "residual_std": fc.residual_std,
            } if fc else {},
        )
        db.add(pred)
        db.flush()

        evidence = []
        for t in hazard.evidence:
            source = db.query(models.Source).get(t.source_id)
            if source is None:
                continue  # hazard/source not provisioned in this theatre — stay honest
            evidence.append(ev_svc.make_evidence(
                db, pred.id, source, t.kind, now - timedelta(hours=t.hours_ago), t.description,
                value=round(comps.get(t.feature_key, 0), 2) if t.feature_key else None))
        pred.evidence_ids = [e.id for e in evidence]

        level = hazard.level(pred.risk_probability)
        existing = db.query(models.Alert).filter_by(location_id=loc.id, resolved=False).count()
        if existing == 0:
            db.add(models.Alert(
                location_id=loc.id, event_type=loc.hazard_type, level=level,
                title=f"{hazard.label} risk {pred.risk_probability:.0%} in {loc.name}",
                summary=f"Forecast horizon {pred.horizon_h}h, severity {pred.severity:.1f}/5, confidence {pred.confidence:.0%}. "
                        f"Top driver: {comps and max(comps, key=lambda k: comps[k])}.",
                prediction_id=pred.id,
            ))
        count += 1
    db.commit()
    return count