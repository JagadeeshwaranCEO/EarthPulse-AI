"""Offline SMS alerting API — register, verify OTP, subscribe, settings, history."""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.db import get_db
from app.core.security import require_api_key
from app.notification import models
from app.notification.providers import PROVIDERS, build_provider
from app.notification.service import SmsService, generate_otp, verify_otp

log = logging.getLogger("earthpulse.sms")

router = APIRouter(prefix="/sms", tags=["sms"])

_E164 = re.compile(r"^\+[1-9]\d{1,14}$")

API_KEY_DEP = require_api_key


def _check_phone(phone: str) -> str:
    phone = phone.strip()
    if not _E164.match(phone):
        raise HTTPException(422, "phone must be E.164, e.g. +919876543210")
    return phone


class RegisterBody(BaseModel):
    phone: str
    name: str | None = None


class VerifyBody(BaseModel):
    phone: str
    otp: str = Field(min_length=4, max_length=8)


class SubscribeBody(BaseModel):
    phone: str
    location_id: str


class SettingsBody(BaseModel):
    phone: str
    enabled: bool | None = None
    min_level: str | None = None
    quiet_hours: bool | None = None


@router.post("/register", dependencies=[API_KEY_DEP])
def register(body: RegisterBody, db: Session = Depends(get_db)):
    """Register a phone and issue an OTP. The phone stays unverified until OTP passes."""
    phone = _check_phone(body.phone)
    service = SmsService(db)
    rec = service.register(phone, body.name)
    _, code = generate_otp(db, phone, ttl_s=get_settings().sms_otp_ttl_s, secret=get_settings().sms_otp_secret)
    _send_otp(db, phone, code)
    return {"phone": phone, "verified": rec.verified, "otp_sent": True}


@router.post("/verify")
def verify(body: VerifyBody, db: Session = Depends(get_db)):
    """Confirm phone ownership with the OTP sent at registration."""
    phone = _check_phone(body.phone)
    if not verify_otp(db, phone, body.otp.strip(), secret=get_settings().sms_otp_secret):
        raise HTTPException(401, "invalid or expired OTP")
    service = SmsService(db)
    service.set_verified(phone)
    return {"phone": phone, "verified": True}


@router.post("/subscribe", dependencies=[API_KEY_DEP])
def subscribe(body: SubscribeBody, db: Session = Depends(get_db)):
    phone = _check_phone(body.phone)
    try:
        SmsService(db).subscribe(phone, body.location_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from None
    return {"phone": phone, "location_id": body.location_id, "subscribed": True}


@router.post("/unsubscribe", dependencies=[API_KEY_DEP])
def unsubscribe(body: SubscribeBody, db: Session = Depends(get_db)):
    phone = _check_phone(body.phone)
    removed = SmsService(db).unsubscribe(phone, body.location_id)
    return {"phone": phone, "location_id": body.location_id, "removed": removed}


@router.patch("/settings", dependencies=[API_KEY_DEP])
def update_settings(body: SettingsBody, db: Session = Depends(get_db)):
    phone = _check_phone(body.phone)
    try:
        rec = SmsService(db).update_settings(phone, enabled=body.enabled, min_level=body.min_level, quiet_hours=body.quiet_hours)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"phone": phone, "enabled": rec.enabled, "min_level": rec.min_level, "quiet_hours": rec.quiet_hours}


@router.post("/test", dependencies=[API_KEY_DEP])
def send_test(body: RegisterBody, db: Session = Depends(get_db)):
    """Send a test SMS to a verified recipient."""
    phone = _check_phone(body.phone)
    try:
        msg = SmsService(db).send_test(phone)
    except ValueError as e:
        raise HTTPException(404, str(e)) from None
    return {"phone": phone, "message_id": msg.id, "status": msg.status, "provider": msg.provider}


@router.delete("/{phone}", dependencies=[API_KEY_DEP])
def remove_recipient(phone: str, db: Session = Depends(get_db)):
    phone = _check_phone(phone)
    removed = SmsService(db).remove(phone)
    if not removed:
        raise HTTPException(404, "recipient not found")
    return {"phone": phone, "removed": True}


@router.get("/recipients", dependencies=[API_KEY_DEP])
def list_recipients(db: Session = Depends(get_db)):
    return [
        {
            "id": r.id,
            "phone": r.phone,
            "name": r.name,
            "verified": r.verified,
            "enabled": r.enabled,
            "min_level": r.min_level,
            "quiet_hours": r.quiet_hours,
            "created_at": r.created_at.isoformat(),
        }
        for r in SmsService(db).recipients()
    ]


@router.get("/history", dependencies=[API_KEY_DEP])
def history(phone: str | None = Query(default=None), limit: int = Query(default=50, le=500), db: Session = Depends(get_db)):
    stmt = select(models.SmsMessage).order_by(models.SmsMessage.created_at.desc()).limit(limit)
    if phone:
        rec = db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone.strip()))
        if rec is None:
            raise HTTPException(404, "recipient not found")
        stmt = (
            select(models.SmsMessage)
            .where(models.SmsMessage.recipient_id == rec.id)
            .order_by(models.SmsMessage.created_at.desc())
            .limit(limit)
        )
    rows = db.scalars(stmt).all()
    return [
        {
            "id": m.id,
            "phone": _phone_of(db, m.recipient_id),
            "kind": m.kind,
            "status": m.status,
            "provider": m.provider,
            "attempts": m.attempts,
            "location_id": m.location_id,
            "event_id": m.event_id,
            "created_at": m.created_at.isoformat(),
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in rows
    ]


@router.get("/audit", dependencies=[API_KEY_DEP])
def audit(limit: int = Query(default=50, le=500), db: Session = Depends(get_db)):
    rows = db.scalars(select(models.SmsAuditLog).order_by(models.SmsAuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": a.id,
            "phone": a.phone,
            "action": a.action,
            "detail": a.detail,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


@router.get("/health")
def provider_health():
    """Which providers are configured and reachable — no credentials exposed."""
    settings = get_settings()
    chain = [n for n in settings.sms_providers.split(",") if n.strip()]
    out = []
    for name in chain:
        provider = build_provider(name.strip(), settings)
        if provider is None:
            out.append({"provider": name.strip(), "configured": False})
            continue
        try:
            ok = provider.health()
        except Exception:
            ok = False
        out.append({"provider": provider.name, "configured": True, "reachable": ok})
    return {"providers": out, "known": sorted(PROVIDERS)}


def _phone_of(db: Session, recipient_id: int) -> str | None:
    rec = db.get(models.SmsRecipient, recipient_id)
    return rec.phone if rec else None


def _send_otp(db: Session, phone: str, code: str) -> None:
    """Send the OTP via the configured chain; failures are logged but non-fatal."""
    settings = get_settings()
    for name in settings.sms_providers.split(","):
        provider = build_provider(name.strip(), settings)
        if provider is None:
            continue
        result = provider.send(phone, f"Your EarthPulse verification code is {code}. Valid {int(settings.sms_otp_ttl_s // 60)} min.", settings.sms_sender_id, settings.sms_provider_timeout_s)
        log.info("OTP to %s via %s: %s", phone, provider.name, "ok" if result.ok else result.error)
        if result.ok:
            return
    log.warning("OTP delivery failed for %s — all providers down", phone)
