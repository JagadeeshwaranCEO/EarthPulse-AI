"""Validation — the platform's precision report card.

Runs the rolling verification pass over the live theatre and returns the
computed skill metrics (Brier, skill vs climatology, ROC AUC, reliability,
sharpness, per-zone tiers). Every number is computed from the seed arc —
forecasts scored against realized telemetry, no narration.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.verification import verify_scope

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("")
def get_validation(scope: str | None = None, db: Session = Depends(get_db)):
    return verify_scope(db, scope)
