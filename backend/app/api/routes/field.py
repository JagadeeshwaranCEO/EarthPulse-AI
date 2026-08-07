"""Field Intel API — submit + triage crowd-sourced ground truth."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ops import publish
from app.core.security import require_api_key
from app.services.field_intel import (
    recent_reports,
    report_summary,
    set_status,
    submit_report,
    vote,
)

router = APIRouter(prefix="/field", tags=["field"])


class ReportBody(BaseModel):
    hazard_type: str = "flood"
    observed_severity: int = Field(ge=0, le=5)
    description: str = Field(min_length=3, max_length=1500)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    medium: str = "web"
    reporter: str | None = None
    image_url: str | None = None


class StatusBody(BaseModel):
    status: str  # pending | confirmed | dismissed


def _dump(db: Session, r) -> dict:
    from app.core import models

    loc = db.get(models.Location, r.location_id) if r.location_id else None
    return {
        "id": r.id,
        "location_id": r.location_id,
        "location_name": loc.name if loc else None,
        "hazard_type": r.hazard_type,
        "observed_severity": r.observed_severity,
        "description": r.description,
        "lat": r.lat,
        "lon": r.lon,
        "distance_km": r.distance_km,
        "agreement": r.agreement,
        "model_risk": r.model_risk,
        "status": r.status,
        "medium": r.medium,
        "image_url": r.image_url,
        "reporter": r.reporter,
        "votes": r.votes,
        "flagged": r.flagged,
        "created_at": r.created_at.isoformat(),
    }


@router.post("/reports", dependencies=[require_api_key])
def create_report(body: ReportBody, db: Session = Depends(get_db)):
    rep = submit_report(
        db,
        hazard_type=body.hazard_type,
        observed_severity=body.observed_severity,
        description=body.description,
        lat=body.lat,
        lon=body.lon,
        medium=body.medium,
        reporter=body.reporter,
        image_url=body.image_url,
    )
    try:
        publish(
            {
                "type": "field_report",
                "action": "created",
                "report_id": rep.id,
                "zone": rep.location_id or "unbound",
                "severity": rep.observed_severity,
                "agreement": rep.agreement,
                "status": rep.status,
            }
        )
    except Exception:
        pass
    return _dump(db, rep)


@router.get("/reports")
def list_reports(
    zone: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
):
    reps = recent_reports(db, zone=zone, status=status, limit=limit)
    return [_dump(db, r) for r in reps]


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    from app.core import models

    row = db.get(models.FieldReport, report_id)
    if row is None:
        raise HTTPException(404, "report not found")
    return _dump(db, row)


@router.post("/reports/{report_id}/vote", dependencies=[require_api_key])
def cast_vote(report_id: int, db: Session = Depends(get_db)):
    rep = vote(db, report_id)
    if rep is None:
        raise HTTPException(404, "report not found")
    return {"id": rep.id, "votes": rep.votes, "flagged": rep.flagged}


@router.patch("/reports/{report_id}/status", dependencies=[require_api_key])
def triage(report_id: int, body: StatusBody, db: Session = Depends(get_db)):
    try:
        rep = set_status(db, report_id, body.status)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    if rep is None:
        raise HTTPException(404, "report not found")
    return _dump(db, rep)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return report_summary(db)