"""Operational scope — switch the command theatre (chennai ↔ tamilnadu) at runtime.

POST /scope clears location-scoped rows, reseeds the target catalog, and re-runs
the full pipeline. The UI can flip the entire theatre without a restart — this is
the seam where real IMD/GPM/reservoir feeds will attach per-district.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_db
from app.core.models import Location
from app.services.refresh import refresh_predictions
from app.services.seeder import reseed

router = APIRouter(prefix="/scope", tags=["scope"])

_SCOPES = {"chennai", "tamilnadu", "wildfire", "india", "asia"}


class ScopeRequest(BaseModel):
    scope: str


@router.get("")
def get_scope(db: Session = Depends(get_db)):
    return {"scope": get_settings().scope, "zones": db.query(Location).count()}


@router.post("")
def set_scope(body: ScopeRequest, db: Session = Depends(get_db)):
    scope = body.scope.strip().lower()
    if scope not in _SCOPES:
        raise HTTPException(400, f"unknown scope '{scope}' — expected {sorted(_SCOPES)}")
    get_settings().scope = scope
    summary = reseed(db, scope)
    refreshed = refresh_predictions(db)
    return {**summary, "predictions": refreshed}
