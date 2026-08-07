"""Live Ops API — aircraft-style summary + merged event feed + ghost log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core import models
from app.core.db import get_db
from app.core.ops import ops_summary, recent
from app.core.security import require_api_key
from app.notification import models as sm

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return ops_summary(db)


@router.get("/events")
def events(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)):
    return recent(db, limit=limit)


@router.get("/ghost")
def ghost_log(limit: int = Query(default=30, le=100), db: Session = Depends(get_db)):
    rows = db.query(models.GhostAction).order_by(models.GhostAction.created_at.desc()).limit(limit).all()
    return [
        {
            "id": g.id,
            "alert_id": g.alert_id,
            "action": g.action,
            "detail": g.detail,
            "recipients": g.recipients,
            "created_at": g.created_at.isoformat(),
        }
        for g in rows
    ]


@router.post("/ghost/toggle", dependencies=[require_api_key])
def toggle_ghost(db: Session = Depends(get_db)):
    """Flip Ghost Mode at runtime (no restart)."""
    from app.config import get_settings

    settings = get_settings()
    settings.ghost_enabled = not settings.ghost_enabled
    return {"ghost_enabled": settings.ghost_enabled}


@router.get("/sms")
def sms_status(db: Session = Depends(get_db)):
    return {
        "recipients": db.query(sm.SmsRecipient).count(),
        "verified": db.query(sm.SmsRecipient).filter(sm.SmsRecipient.verified == True).count(),  # noqa: E712
        "messages": db.query(sm.SmsMessage).count(),
        "sent": db.query(sm.SmsMessage).filter(sm.SmsMessage.status == "sent").count(),
        "delivery_attempts": db.query(sm.SmsDeliveryAttempt).count(),
        "subscriptions": db.query(sm.SmsSubscription).count(),
    }