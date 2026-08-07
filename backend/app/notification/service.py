"""Notification service — decides, templates, dedupes and delivers SMS alerts.

The prediction pipeline writes `Alert` rows; this service is the only consumer
that turns them into SMS. It is provider-agnostic (see providers.py) and keeps
its own delivery state so the pipeline never knows a phone exists.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models as core_models
from app.core.security import SlidingWindowRateLimiter
from app.notification import models
from app.notification.providers import build_provider

log = logging.getLogger("earthpulse.sms")

_LEVEL_RANK = {"advisory": 0, "watch": 1, "warning": 2, "critical": 3}

DEFAULT_TEMPLATE = """EARTHPULSE ALERT
Zone: {zone}
{hazard} Risk: {probability}%
{guidance}
Confidence: {confidence}%
Stay away from low-lying areas."""

_GUIDANCE = {
    "flood": "Evacuate immediately.",
    "wildfire": "Evacuate immediately.",
    "cyclone": "Seek shelter now.",
    "earthquake": "Drop, cover, hold on.",
    "landslide": "Move to higher ground.",
    "tsunami": "Move inland immediately.",
    "heatwave": "Stay indoors, hydrate.",
    "volcanic": "Follow ash advisories.",
    "drought": "Conserve water supplies.",
}

# Per-recipient + global send throttle (sliding window, in-memory).
_recipient_limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0)
_global_limiter = SlidingWindowRateLimiter(limit=60, window_s=60.0)


class SmsService:
    def __init__(self, db: Session):
        self.db = db

    # ---- registration / preferences -----------------------------------------

    def register(self, phone: str, name: str | None = None) -> models.SmsRecipient:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            rec = models.SmsRecipient(phone=phone, name=name)
            self.db.add(rec)
        elif name:
            rec.name = name
        self.db.commit()
        self._audit(phone, "register", "recipient registered")
        return rec

    def set_verified(self, phone: str) -> models.SmsRecipient:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            raise ValueError("recipient not registered")
        rec.verified = True
        self.db.commit()
        self._audit(phone, "verify", "phone verified")
        return rec

    def update_settings(self, phone: str, *, enabled: bool | None = None, min_level: str | None = None, quiet_hours: bool | None = None) -> models.SmsRecipient:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            raise ValueError("recipient not registered")
        if enabled is not None:
            rec.enabled = enabled
        if min_level is not None:
            if min_level not in _LEVEL_RANK:
                raise ValueError(f"unknown min_level '{min_level}'")
            rec.min_level = min_level
        if quiet_hours is not None:
            rec.quiet_hours = quiet_hours
        self.db.commit()
        self._audit(phone, "settings", f"settings updated: enabled={rec.enabled} min_level={rec.min_level} quiet={rec.quiet_hours}")
        return rec

    def subscribe(self, phone: str, location_id: str) -> models.SmsSubscription:
        rec = self._verified_recipient(phone)
        loc = self.db.get(core_models.Location, location_id)
        if loc is None:
            raise ValueError(f"unknown location '{location_id}'")
        sub = self.db.scalar(
            select(models.SmsSubscription).where(
                models.SmsSubscription.recipient_id == rec.id,
                models.SmsSubscription.location_id == location_id,
            )
        )
        if sub is None:
            sub = models.SmsSubscription(recipient_id=rec.id, location_id=location_id)
            self.db.add(sub)
            self.db.commit()
            self._audit(phone, "subscribe", f"subscribed to {location_id}")
        return sub

    def unsubscribe(self, phone: str, location_id: str) -> bool:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            return False
        sub = self.db.scalar(
            select(models.SmsSubscription).where(
                models.SmsSubscription.recipient_id == rec.id,
                models.SmsSubscription.location_id == location_id,
            )
        )
        if sub is not None:
            self.db.delete(sub)
            self.db.commit()
            self._audit(phone, "unsubscribe", f"unsubscribed from {location_id}")
            return True
        return False

    def remove(self, phone: str) -> bool:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            return False
        self.db.query(models.SmsSubscription).filter(models.SmsSubscription.recipient_id == rec.id).delete()
        self.db.delete(rec)
        self.db.commit()
        self._audit(phone, "remove", "recipient removed")
        return True

    def recipients(self) -> list[models.SmsRecipient]:
        return list(self.db.scalars(select(models.SmsRecipient).order_by(models.SmsRecipient.created_at.desc())))

    # ---- alert pipeline ------------------------------------------------------

    def process_alert(self, alert: core_models.Alert) -> int:
        """Evaluate one new alert against every subscription; return SMS count sent."""
        settings = get_settings()
        sent = 0
        pred = self.db.get(core_models.Prediction, alert.prediction_id) if alert.prediction_id else None
        probability = pred.risk_probability if pred else 0.0
        confidence = pred.confidence if pred else 0.0
        severity = pred.severity if pred else 0.0
        loc = self.db.get(core_models.Location, alert.location_id)

        if probability < settings.sms_risk_threshold:
            return 0
        if _LEVEL_RANK.get(alert.level, 0) < _LEVEL_RANK.get(settings.sms_min_level, 1):
            return 0

        subs = self.db.scalars(
            select(models.SmsSubscription).where(models.SmsSubscription.location_id == alert.location_id)
        ).all()
        for sub in subs:
            rec = self.db.get(models.SmsRecipient, sub.recipient_id)
            if rec is None or not rec.verified or not rec.enabled:
                continue
            if _LEVEL_RANK.get(alert.level, 0) < _LEVEL_RANK.get(rec.min_level, 1):
                continue
            if rec.quiet_hours and self._in_quiet_hours():
                self._audit(rec.phone, "suppress", f"quiet hours — {alert.location_id}")
                continue
            if self._is_duplicate(rec, alert, probability):
                continue
            if self._deliver(rec, alert, loc, probability, confidence, severity):
                sent += 1
        return sent

    def _deliver(self, rec, alert, loc, probability, confidence, severity) -> bool:
        settings = get_settings()
        phone = rec.phone
        if not _recipient_limiter.hit(phone) or not _global_limiter.hit("global"):
            self._audit(phone, "suppress", "rate limit")
            return False

        body = self._render(
            loc.name if loc else alert.location_id,
            alert.event_type,
            probability,
            confidence,
            severity,
        )
        msg = models.SmsMessage(
            recipient_id=rec.id,
            location_id=alert.location_id,
            event_id=alert.id,
            kind="alert",
            body=body,
            status="queued",
            risk_probability=probability,
        )
        self.db.add(msg)
        self.db.flush()
        self._deliver_with_retry(msg, phone, body, settings)
        self.db.commit()
        return msg.status == "sent"

    def _deliver_with_retry(self, msg, phone, body, settings) -> None:
        providers = self._provider_chain(settings)
        if not providers:
            msg.status = "failed"
            self._audit(phone, "failover", "no providers configured")
            return
        attempt = 0
        delay = settings.sms_retry_base_seconds
        for provider in providers:
            attempt += 1
            msg.attempts = attempt
            result = provider.send(phone, body, settings.sms_sender_id, settings.sms_provider_timeout_s)
            self.db.add(
                models.SmsDeliveryAttempt(
                    message_id=msg.id,
                    attempt_no=attempt,
                    provider=provider.name,
                    provider_ref=result.provider_ref,
                    ok=result.ok,
                    error=result.error,
                )
            )
            log.info("SMS attempt %d via %s -> %s (%s)", attempt, provider.name, "ok" if result.ok else "fail", result.error or "")
            if result.ok:
                msg.status = "sent"
                msg.provider = provider.name
                msg.sent_at = datetime.now(timezone.utc)
                self._audit(phone, "send", f"sent via {provider.name} ref={result.provider_ref}")
                return
            self._audit(phone, "failover", f"{provider.name} failed: {result.error}")
            if attempt < len(providers) + settings.sms_retry_count - 1:
                self._sleep(delay)
                delay = min(delay * 2, settings.sms_retry_max_seconds)
        msg.status = "failed"
        self._audit(phone, "send", "all providers exhausted")

    def send_test(self, phone: str) -> models.SmsMessage:
        """Send a test SMS to a verified recipient (no alert involved)."""
        rec = self._verified_recipient(phone)
        settings = get_settings()
        body = self._render("TEST", "flood", 1.0, 1.0, 5.0, test=True)
        msg = models.SmsMessage(recipient_id=rec.id, kind="test", body=body, status="queued")
        self.db.add(msg)
        self.db.flush()
        self._deliver_with_retry(msg, phone, body, settings)
        self.db.commit()
        return msg

    # ---- helpers -------------------------------------------------------------

    def _provider_chain(self, settings) -> list:
        chain: list = []
        for name in settings.sms_providers.split(","):
            provider = build_provider(name.strip(), settings)
            if provider is not None:
                chain.append(provider)
        if not chain:
            log.warning("SMS: no usable provider (SMS_PROVIDERS=%s)", settings.sms_providers)
        return chain

    def _is_duplicate(self, rec, alert, probability) -> bool:
        prev = self.db.scalar(
            select(models.SmsMessage)
            .where(models.SmsMessage.recipient_id == rec.id, models.SmsMessage.location_id == alert.location_id, models.SmsMessage.event_id == alert.id)
            .limit(1)
        )
        if prev is not None:
            return True
        last = self.db.scalar(
            select(models.SmsMessage)
            .where(
                models.SmsMessage.recipient_id == rec.id,
                models.SmsMessage.location_id == alert.location_id,
                models.SmsMessage.kind == "alert",
            )
            .order_by(models.SmsMessage.created_at.desc())
            .limit(1)
        )
        if last is not None and last.risk_probability is not None:
            delta = abs(probability - last.risk_probability)
            if delta < get_settings().sms_resend_delta:
                self._audit(rec.phone, "suppress", f"dup {alert.location_id} delta={delta:.2f}")
                return True
        return False

    def _in_quiet_hours(self) -> bool:
        window = get_settings().sms_quiet_hours
        if not window:
            return False
        try:
            start_s, end_s = window.split("-")
            start = datetime.strptime(start_s.strip(), "%H:%M").time()
            end = datetime.strptime(end_s.strip(), "%H:%M").time()
        except Exception:
            return False
        now = datetime.now(timezone.utc).time()
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def _render(self, zone: str, hazard: str, probability: float, confidence: float, severity: float, test: bool = False) -> str:
        template = get_settings().sms_template or DEFAULT_TEMPLATE
        guidance = _GUIDANCE.get(hazard, "Evacuate immediately.")
        if test:
            return "EARTHPULSE TEST — SMS delivery check. No action needed."
        return template.format(
            zone=zone,
            hazard=hazard.title(),
            probability=int(round(probability * 100)),
            confidence=int(round(confidence * 100)),
            severity=severity,
            guidance=guidance,
        )

    def _verified_recipient(self, phone: str) -> models.SmsRecipient:
        rec = self.db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        if rec is None:
            raise ValueError("recipient not registered")
        if not rec.verified:
            raise ValueError("phone not verified")
        return rec

    def _audit(self, phone: str | None, action: str, detail: str) -> None:
        self.db.add(models.SmsAuditLog(phone=phone, action=action, detail=detail))

    def _sleep(self, seconds: float) -> None:
        time.sleep(seconds)


# ---- OTP -------------------------------------------------------------------

def naive_utc(value: datetime | None = None) -> datetime:
    """SQLite returns naive datetimes; Postgres returns aware ones. Normalize to naive UTC for comparisons."""
    dt = value if value is not None else datetime.now(timezone.utc)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def hash_otp(code: str, salt: str = "") -> str:
    return hashlib.sha256(f"{code}:{salt}".encode()).hexdigest()


def generate_otp(db: Session, phone: str, ttl_s: int = 600, secret: str = "") -> tuple[models.SmsOtp, str]:
    code = f"{time.time_ns() % 1000000:06d}"
    otp = models.SmsOtp(
        phone=phone,
        code_hash=hash_otp(code, secret),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_s),
    )
    db.add(otp)
    db.commit()
    return otp, code


def verify_otp(db: Session, phone: str, code: str, secret: str = "") -> bool:
    now = naive_utc()
    rows = db.scalars(
        select(models.SmsOtp)
        .where(models.SmsOtp.phone == phone, models.SmsOtp.consumed == False)  # noqa: E712
        .order_by(models.SmsOtp.created_at.desc())
    ).all()
    for otp in rows:
        if naive_utc(otp.expires_at) < now:
            continue
        otp.attempts += 1
        if otp.attempts > 5:
            db.commit()
            return False
        if otp.code_hash == hash_otp(code, secret):
            otp.consumed = True
            db.commit()
            return True
        db.commit()
    return False
