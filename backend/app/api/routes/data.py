"""Real-data ingestion status & trigger endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_api_key
from app.services.ingest import registry

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/sources")
def list_sources():
    return {"adapters": registry.statuses()}


@router.post("/ingest", dependencies=[require_api_key])
def trigger_ingest(db: Session = Depends(get_db)):
    return {"ingested": registry.ingest_once(db)}