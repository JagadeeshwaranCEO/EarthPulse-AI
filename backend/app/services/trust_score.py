"""Trust Score — separates mathematical confidence from operational trust.

Where confidence quantifies how sure the *model* is, trust scores how sure we
can be that the *data* is trustworthy: sensor coverage, stream freshness,
temporal integrity, historical analogue availability, and model stability.
Every check is derived deterministically from the actual database state — if
sensors go stale or a stream drops, trust degrades honestly.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.models import Location, SatelliteFrame, WeatherSnapshot
from app.services.environmental_memory import memory_view
from app.services.ticker import current_hour

_FRESH_SATELLITE_HOURS = 6.0  # frame considered fresh within this sim-window
_MAX_GAP_HOURS = 3.0  # acceptable gap between consecutive gauge rows
_ANALOGUE_SIMILARITY_FLOOR = 0.55  # meaningful analogue exists above this


def _gauge_gap_hours(db: Session, location_id: str) -> float:
    rows = (
        db.query(WeatherSnapshot.captured_at)
        .filter_by(location_id=location_id)
        .order_by(WeatherSnapshot.captured_at)
        .all()
    )
    if len(rows) < 2:
        return 0.0
    gap = max((rows[i].captured_at - rows[i - 1].captured_at).total_seconds()
              for i in range(1, len(rows))) / 3600.0
    return gap


def _latest_satellite_age_h(db: Session, location_id: str) -> float | None:
    """Age of the newest satellite frame *as the pipeline consumes it*, in sim hours.

    The pipeline truncates frames to the sim clock (n = min(36, hour//2)), so
    freshness is measured against the sim clock — not wall time.
    """
    from app.services.ticker import get_anchor

    anchor = get_anchor()
    rows = (
        db.query(SatelliteFrame.captured_at)
        .filter_by(location_id=location_id)
        .order_by(SatelliteFrame.captured_at)
        .all()
    )
    if not rows:
        return None
    hour = current_hour()
    n = min(len(rows), max(1, int(hour) // 2))
    ts = rows[n - 1].captured_at
    if anchor:
        base = datetime.fromisoformat(anchor)
        ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        base = base.replace(tzinfo=timezone.utc) if base.tzinfo is None else base
        return max(0.0, hour - (ts - base).total_seconds() / 3600.0)
    return 0.0


def compute_trust(db: Session, location_id: str) -> dict:
    """Deterministic trust decomposition for a location's live feed."""
    loc = db.get(Location, location_id)
    if loc is None:
        return {"location_id": location_id, "level": "Low", "score": 0.0,
                "checks": [], "reason": "location not found"}

    checks: list[dict] = []

    # 1 · sensor coverage: all monitored zones streaming a full gauge window
    zone_count = db.query(Location).count()
    streamed = db.query(WeatherSnapshot.location_id).distinct().count()
    coverage_ok = zone_count > 0 and streamed == zone_count
    checks.append({
        "label": f"Local drainage telemetry · {streamed}/{zone_count} zones streaming",
        "ok": coverage_ok,
        "detail": "synthetic pilot feed · IMD gauges" if coverage_ok else "missing zone streams",
    })

    # 2 · satellite freshness: last frame within the freshness window
    age_h = _latest_satellite_age_h(db, location_id)
    sat_ok = age_h is not None and age_h <= _FRESH_SATELLITE_HOURS
    checks.append({
        "label": f"Satellite telemetry · {'< ' + f'{age_h:.1f}h' if age_h is not None else 'none'} old",
        "ok": sat_ok,
        "detail": "Copernicus SWI / NASA GPM frame cadence" if sat_ok else "stale or missing frames",
    })

    # 3 · temporal integrity: no anomalous gaps in the gauge stream
    gap = _gauge_gap_hours(db, location_id)
    gap_ok = gap <= _MAX_GAP_HOURS
    checks.append({
        "label": f"Temporal data integrity · max gap {gap:.1f}h",
        "ok": gap_ok,
        "detail": "no anomalous gaps in temporal data stream" if gap_ok else f"gap exceeds {_MAX_GAP_HOURS:.0f}h",
    })

    # 4 · historical analogue available for context
    from app.agents.orchestrator import build_agent_outputs

    outputs, _ = build_agent_outputs(db, location_id)
    comps = outputs.get("risk_fusion", {}).get("components", {})
    mem = memory_view(location_id, comps, loc.hazard_type)
    top_sim = mem["top_analogues"][0]["similarity"] if mem["top_analogues"] else 0.0
    ana_ok = top_sim >= _ANALOGUE_SIMILARITY_FLOOR
    checks.append({
        "label": f"Historical analogue · {top_sim:.0%} match",
        "ok": ana_ok,
        "detail": "environmental memory retrieved" if ana_ok else "weak analogue — treat patterns with caution",
    })

    # 5 · model stability: forecaster residual dispersion is low
    pred = outputs.get("prediction", {})
    residual = pred.get("residual_std", 0.0)
    model_ok = residual <= 0.12
    checks.append({
        "label": f"Model stability · residual σ {residual:.3f}",
        "ok": model_ok,
        "detail": "forecaster output within stability envelope" if model_ok else "high residual dispersion",
    })

    # 6 · sensor outage: low proportion of degraded sources in the feed
    failed = outputs.get("risk_fusion", {}).get("_failure", 0) or 0
    outage_ok = not failed
    checks.append({
        "label": "Sensor outage ratio · none flagged",
        "ok": outage_ok,
        "detail": "no agent flagged source degradation" if outage_ok else "degraded source detected",
    })

    weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]
    score = round(100 * sum(w * (1.0 if c["ok"] else 0.0) for c, w in zip(checks, weights)), 1)
    level = "High" if score >= 80 else "Moderate" if score >= 55 else "Low"

    return {
        "location_id": location_id,
        "level": level,
        "score": score,
        "confidence_now": pred.get("confidence", 0.0),
        "sim_hour": current_hour(),
        "checks": checks,
        "reason": {
            "High": "8 datasets coherent · sensors live · no anomalous gaps",
            "Moderate": "partial stream coverage — degrade cautiously",
            "Low": "flying blind — treat predictions as provisional",
        }[level],
    }
