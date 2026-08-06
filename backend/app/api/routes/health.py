"""Health & readiness — liveness for orchestrators, readiness for load balancers.

`/health` is deliberately side-effect-free and always 200 while the process is
up. `/ready` actually touches the DB and the seed catalog so a consumer can tell
whether the API is serving real predictions yet.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Location

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        zones = db.query(Location).count()
    except Exception:
        return {"status": "not_ready", "reason": "database unavailable"}, 503
    if zones == 0:
        return {"status": "not_ready", "reason": "no seed data"}, 503
    return {"status": "ready", "zones": zones}
