"""Field intel — crowd-sourced ground truth bound to the model theatre.

A report is carried by (latitude, longitude). We haversine-bind it to the
nearest zone centroid, pull that zone's latest prediction, and score
`agreement` = how well the report supports (or contradicts) the model signal.
High-agreement reports auto-confirm; the operator feed is ranked by agreement
+ severity so ground truth rises to the top.
"""

from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import models


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two coordinates in kilometres."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


def _nearest_zone(db: Session, lat: float, lon: float, max_km: float) -> tuple[models.Location | None, float]:
    best, best_d = None, None
    for loc in db.query(models.Location).all():
        d = haversine_km(lat, lon, loc.lat, loc.lon)
        if best_d is None or d < best_d:
            best, best_d = loc, d
    if best_d is None or best_d > max_km:
        return None, best_d or 0.0
    return best, best_d


def _latest_prediction(db: Session, location_id: str) -> models.Prediction | None:
    stmt = (
        select(models.Prediction)
        .where(models.Prediction.location_id == location_id)
        .order_by(models.Prediction.generated_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def score_agreement(model_risk: float, observed_severity: int) -> float:
    """0..1 correlation between what the model says and what people see.

    High risk + severe report (or low risk + mild report) → agree. Mismatched
    signals score low (true ground truth that the model is missing).
    """
    severity_norm = max(0.0, min(1.0, observed_severity / 5.0))
    return round(1.0 - abs(model_risk - severity_norm), 3)


def submit_report(
    db: Session,
    *,
    hazard_type: str,
    observed_severity: int,
    description: str,
    lat: float,
    lon: float,
    medium: str = "web",
    reporter: str | None = None,
    image_url: str | None = None,
    auto_confirm: float | None = None,
) -> models.FieldReport:
    """Persist a field report, bind to nearest zone, score agreement, auto-confirm."""
    from app.config import get_settings

    settings = get_settings()
    loc, dist = _nearest_zone(db, lat, lon, settings.field_geo_radius_km)

    model_risk = 0.0
    if loc is not None:
        pred = _latest_prediction(db, loc.id)
        model_risk = pred.risk_probability if pred else 0.0

    agreement = score_agreement(model_risk, observed_severity)
    threshold = settings.field_auto_confirm_agreement if auto_confirm is None else auto_confirm

    report = models.FieldReport(
        location_id=loc.id if loc else None,
        hazard_type=hazard_type,
        observed_severity=max(0, min(5, int(observed_severity))),
        description=description[:1500],
        lat=lat,
        lon=lon,
        distance_km=dist,
        agreement=agreement,
        medium=medium,
        image_url=image_url[:2000] if image_url else None,
        reporter=reporter[:80] if reporter else None,
        status="confirmed" if agreement >= threshold and loc is not None else "pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def set_status(db: Session, report_id: int, status: str) -> models.FieldReport | None:
    rep = db.get(models.FieldReport, report_id)
    if rep is None:
        return None
    if status not in ("pending", "confirmed", "dismissed"):
        raise ValueError(f"invalid status {status!r}")
    rep.status = status
    db.commit()
    db.refresh(rep)
    return rep


def vote(db: Session, report_id: int, delta: int = 1) -> models.FieldReport | None:
    rep = db.get(models.FieldReport, report_id)
    if rep is None:
        return None
    rep.votes = max(-50, min(50, rep.votes + max(-5, min(5, delta))))
    if rep.votes <= -3:
        rep.flagged = True
    db.commit()
    db.refresh(rep)
    return rep


def recent_reports(db: Session, *, zone: str | None = None, status: str | None = None, limit: int = 50) -> list[models.FieldReport]:
    stmt = select(models.FieldReport)
    if zone:
        stmt = stmt.where(models.FieldReport.location_id == zone)
    if status:
        stmt = stmt.where(models.FieldReport.status == status)
    stmt = stmt.order_by(models.FieldReport.created_at.desc()).limit(max(1, min(500, limit)))
    return list(db.scalars(stmt))


def report_summary(db: Session) -> dict:
    """Counts + calibration signal (reports per zone vs model risk)."""
    rows = db.query(models.FieldReport).all()
    by_status: dict[str, int] = {}
    by_zone: dict[str, dict] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        key = r.location_id or "unbound"
        entry = by_zone.setdefault(key, {"reports": 0, "severity_sum": 0, "confirmed": 0, "avg_agreement": 0.0})
        entry["reports"] += 1
        entry["severity_sum"] += r.observed_severity
        entry["confirmed"] += 1 if r.status == "confirmed" else 0
        entry["avg_agreement"] += r.agreement
    for entry in by_zone.values():
        entry["avg_severity"] = round(entry["severity_sum"] / max(1, entry["reports"]), 2)
        entry["avg_agreement"] = round(entry["avg_agreement"] / max(1, entry["reports"]), 3)

    def _zone_name(zid: str) -> str:
        loc = db.get(models.Location, zid)
        return loc.name if loc else zid

    return {
        "total": len(rows),
        "confirmed": by_status.get("confirmed", 0),
        "pending": by_status.get("pending", 0),
        "dismissed": by_status.get("dismissed", 0),
        "flagged": sum(1 for r in rows if r.flagged),
        "zones": [
            {"location_id": zid, "location_name": _zone_name(zid), **entry}
            for zid, entry in sorted(by_zone.items(), key=lambda kv: kv[1]["reports"], reverse=True)
        ],
    }