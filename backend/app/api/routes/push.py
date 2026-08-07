"""Web Push API — public key, subscriptions, and a guarded broadcast."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models
from app.core.db import get_db
from app.core.ops import publish
from app.core.security import require_api_key
from app.services.push import get_or_create_keys, push_message, send_webpush, vapid_public_point_b64

router = APIRouter(prefix="/push", tags=["push"])


class SubscribeBody(BaseModel):
    endpoint: str = Field(min_length=8, max_length=2000)
    p256dh: str = Field(min_length=8, max_length=1000)
    auth: str = Field(min_length=4, max_length=200)
    ua: str = ""


class PushTestBody(BaseModel):
    title: str = Field(default="EarthPulse test", max_length=120)
    body: str = Field(default="Alerts are working. This is a test push.", max_length=500)


class UnsubscribeBody(BaseModel):
    endpoint: str


@router.get("/public")
def public_key(db: Session = Depends(get_db)):
    const, pub_pem = get_or_create_keys(db)
    return {
        "enabled": get_settings().push_enabled,
        "vapid_public_key": vapid_public_point_b64(pub_pem) if get_settings().push_enabled else None,
        "application_server": "earthpulse",
    }


@router.post("/register", dependencies=[require_api_key])
def register(body: SubscribeBody, db: Session = Depends(get_db)):
    existing = db.scalar(select(models.PushSubscription).where(models.PushSubscription.endpoint == body.endpoint))
    if existing is None:
        existing = models.PushSubscription(endpoint=body.endpoint, p256dh=body.p256dh, auth=body.auth, ua=body.ua)
        db.add(existing)
    else:
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.ua = body.ua[:200]
    db.commit()
    db.refresh(existing)
    return {"registered": True, "id": existing.id}


@router.post("/unregister", dependencies=[require_api_key])
def unregister(body: UnsubscribeBody, db: Session = Depends(get_db)):
    row = db.scalar(select(models.PushSubscription).where(models.PushSubscription.endpoint == body.endpoint))
    if row is not None:
        db.delete(row)
        db.commit()
    return {"registered": False}


@router.get("/count")
def count(db: Session = Depends(get_db)):
    return {"subscriptions": db.query(models.PushSubscription).count()}


@router.post("/test", dependencies=[require_api_key])
def send_test(body: PushTestBody, db: Session = Depends(get_db)):
    if not get_settings().push_enabled:
        raise HTTPException(503, "push disabled")
    priv_pem, pub_pem = get_or_create_keys(db)
    subs = db.query(models.PushSubscription).limit(200).all()
    payload = push_message(body.title, body.body, tag="earthpulse-test")
    results = []
    for sub in subs:
        res = send_webpush(
            sub.endpoint,
            sub.p256dh,
            sub.auth,
            payload,
            priv_pem,
            pub_pem,
            ttl_s=get_settings().push_ttl_seconds,
            contact=get_settings().push_contact,
        )
        results.append({"id": sub.id, **res})
        if res["ok"]:
            sub.last_seen_at = models.utcnow()
        elif res.get("status") in (404, 410):
            db.delete(sub)
    db.commit()
    ok = sum(1 for r in results if r["ok"])
    try:
        publish({"type": "push", "action": "test", "sent": ok, "subscriptions": len(results)})
    except Exception:
        pass
    return {"sent": ok, "attempted": len(results), "results": results}