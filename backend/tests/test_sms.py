"""Tests for the offline SMS notification module — registration, OTP, delivery, dedup."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.core.db import SessionLocal
from app.main import app
from app.notification import models
from app.notification.providers import LogProvider, build_provider
from app.notification.service import hash_otp

TEST_OTP = "123456"


def _fixed_otp(db, phone, ttl_s=600, secret=""):
    """Stand-in for the real generate_otp: predictable code so tests can verify via the API."""
    otp = models.SmsOtp(
        phone=phone,
        code_hash=hash_otp(TEST_OTP, secret),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=ttl_s),
    )
    db.add(otp)
    db.commit()
    return otp, TEST_OTP


@pytest.fixture(scope="module")
def client():
    from app.core.security import reset_mutation_limiters
    from app.services import ticker

    ticker.reset()
    reset_mutation_limiters()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def seeded(client):
    db = SessionLocal()
    try:
        from app.core.models import Location
        from app.services.seeder import seed_if_empty

        if db.query(Location).count() == 0:
            seed_if_empty(db, get_settings())
        yield db
    finally:
        db.close()


@pytest.fixture
def fixed_otp(monkeypatch):
    import app.api.routes.sms as sms_routes

    monkeypatch.setattr(sms_routes, "generate_otp", _fixed_otp)


def _settings_enabled(sms_enabled=True, providers="log"):
    s = get_settings()
    s.sms_enabled = sms_enabled
    s.sms_providers = providers
    s.sms_risk_threshold = 0.5
    s.sms_min_level = "watch"
    s.sms_resend_delta = 0.2
    return s


def _register_verify(client, phone):
    assert client.post("/api/v1/sms/register", json={"phone": phone}).status_code == 200
    v = client.post("/api/v1/sms/verify", json={"phone": phone, "otp": TEST_OTP})
    assert v.status_code == 200
    assert v.json()["verified"] is True


def _clean(db, phone: str, location_id: str):
    """Remove leftover suite state so each test sees a deterministic world."""
    from app.core import models as cm

    rec = db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
    if rec is not None:
        db.query(models.SmsSubscription).filter(models.SmsSubscription.recipient_id == rec.id).delete()
        db.query(models.SmsMessage).filter(models.SmsMessage.recipient_id == rec.id).delete()
    db.query(cm.Alert).filter(cm.Alert.location_id == location_id).delete()
    db.commit()


def test_provider_factory():
    from app.config import get_settings

    assert isinstance(build_provider("log", get_settings()), LogProvider)
    assert build_provider("twilio", get_settings()) is None  # no creds configured


def test_register_verify_subscribe_roundtrip(client, seeded, fixed_otp):
    _settings_enabled()
    phone = "+919876543210"

    r = client.post("/api/v1/sms/register", json={"phone": phone, "name": "Test User"})
    assert r.status_code == 200
    assert r.json()["otp_sent"] is True

    # wrong OTP rejected
    assert client.post("/api/v1/sms/verify", json={"phone": phone, "otp": "000000"}).status_code == 401

    # correct OTP verifies
    v = client.post("/api/v1/sms/verify", json={"phone": phone, "otp": TEST_OTP})
    assert v.status_code == 200
    assert v.json()["verified"] is True

    db = SessionLocal()
    try:
        rec = db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        assert rec is not None and rec.verified
    finally:
        db.close()

    sub = client.post("/api/v1/sms/subscribe", json={"phone": phone, "location_id": "mylapore"})
    assert sub.status_code == 200
    assert client.post("/api/v1/sms/subscribe", json={"phone": phone, "location_id": "nowhere"}).status_code == 404

    # settings update
    up = client.patch("/api/v1/sms/settings", json={"phone": phone, "min_level": "critical", "quiet_hours": True})
    assert up.status_code == 200
    assert up.json()["min_level"] == "critical"

    # test SMS delivered via log provider
    t = client.post("/api/v1/sms/test", json={"phone": phone})
    assert t.status_code == 200
    assert t.json()["status"] == "sent"

    # history lists it
    h = client.get("/api/v1/sms/history", params={"phone": phone})
    assert h.status_code == 200
    assert len(h.json()) >= 1  # the test SMS
    assert h.json()[0]["kind"] == "test"

    # recipients list
    recs = client.get("/api/v1/sms/recipients")
    assert any(x["phone"] == phone for x in recs.json())

    # unsubscribe + remove
    assert client.post("/api/v1/sms/unsubscribe", json={"phone": phone, "location_id": "mylapore"}).status_code == 200
    assert client.delete(f"/api/v1/sms/{phone}").status_code == 200


def test_e164_validation(client):
    bad = client.post("/api/v1/sms/register", json={"phone": "9876543210"})
    assert bad.status_code == 422


def test_provider_health(client):
    _settings_enabled()
    h = client.get("/api/v1/sms/health")
    assert h.status_code == 200
    body = h.json()
    assert "log" in body["known"]
    assert any(p["provider"] == "log" and p["configured"] for p in body["providers"])


def test_alert_to_sms_pipeline(client, seeded, fixed_otp):
    """A critical alert above threshold reaches a subscribed, verified recipient."""
    from app.core import models as cm

    _settings_enabled()
    phone = "+919876543299"
    zone = "guindy"
    db = SessionLocal()
    try:
        _clean(db, phone, zone)
        _register_verify(client, phone)

        rec = db.scalar(select(models.SmsRecipient).where(models.SmsRecipient.phone == phone))
        svc = __import__("app.notification.service", fromlist=["SmsService"]).SmsService(db)
        svc.subscribe(phone, zone)
        sub = db.scalar(
            select(models.SmsSubscription).where(
                models.SmsSubscription.recipient_id == rec.id,
                models.SmsSubscription.location_id == zone,
            )
        )
        assert sub is not None

        pred = cm.Prediction(
            location_id=zone,
            event_type="flood",
            generated_at=dt.datetime.now(dt.timezone.utc),
            risk_probability=0.95,
            confidence=0.9,
            severity=4.0,
            horizon_h=12,
        )
        db.add(pred)
        db.flush()
        alert = cm.Alert(
            location_id=zone,
            event_type="flood",
            level="critical",
            title="Flood risk 95% in Guindy",
            summary="critical test alert",
            prediction_id=pred.id,
        )
        db.add(alert)
        db.commit()

        from app.notification.listener import scan_new_alerts

        assert scan_new_alerts(db) >= 1

        msg = db.scalar(
            select(models.SmsMessage)
            .where(models.SmsMessage.recipient_id == rec.id, models.SmsMessage.event_id == alert.id)
            .limit(1)
        )
        assert msg is not None
        assert msg.status == "sent"
        assert msg.provider == "log"
        assert "95%" in msg.body and "Guindy" in msg.body

        # duplicate suppression: same alert is not re-sent
        assert scan_new_alerts(db) == 0
    finally:
        db.close()


def test_alert_below_threshold_no_sms(client, seeded, fixed_otp):
    from app.core import models as cm

    _settings_enabled()
    phone = "+919876543288"
    zone = "velachery"
    db = SessionLocal()
    try:
        _clean(db, phone, zone)
        _register_verify(client, phone)
        svc = __import__("app.notification.service", fromlist=["SmsService"]).SmsService(db)
        svc.subscribe(phone, zone)
        pred = cm.Prediction(
            location_id=zone,
            event_type="flood",
            generated_at=dt.datetime.now(dt.timezone.utc),
            risk_probability=0.3,
            confidence=0.9,
            severity=2.0,
            horizon_h=12,
        )
        db.add(pred)
        db.flush()
        alert = cm.Alert(
            location_id=zone,
            event_type="flood",
            level="watch",
            title="low",
            summary="below",
            prediction_id=pred.id,
        )
        db.add(alert)
        db.commit()
        from app.notification.listener import scan_new_alerts

        assert scan_new_alerts(db) == 0
    finally:
        db.close()
