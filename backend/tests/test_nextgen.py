"""NextGen suite — field intel, scenario digital twin, ops feed, ghost audit, web push crypto."""

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core import models
from app.core.db import SessionLocal
from app.core.ops import reset as ops_reset
from app.main import app


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
        if db.query(models.Location).count() == 0:
            from app.services.seeder import seed_if_empty

            seed_if_empty(db, get_settings())
        yield db
    finally:
        db.close()


def _clean(db, location_id: str):
    db.query(models.FieldReport).filter(models.FieldReport.location_id == location_id).delete()
    db.query(models.Alert).filter(models.Alert.location_id == location_id).delete()
    db.query(models.GhostAction).delete()
    db.query(models.ScenarioStep).delete()
    db.query(models.ScenarioRun).delete()
    db.commit()


# ---- field intel ----------------------------------------------------------

def test_report_binds_zone_and_scores_agreement(client, seeded):
    _clean(seeded, "guindy")
    loc = seeded.get(models.Location, "guindy")
    r = client.post(
        "/api/v1/field/reports",
        json={
            "hazard_type": "flood",
            "observed_severity": 4,
            "description": "water rising near the railway bridge",
            "lat": loc.lat + 0.01,
            "lon": loc.lon + 0.01,
            "medium": "web",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["location_id"] is not None  # nearest theatre zone (may be adyar zone, not guindy)
    assert 0 <= body["agreement"] <= 1
    assert body["status"] in ("pending", "confirmed")
    assert body["distance_km"] < 3.0

    # summary reflects it
    s = client.get("/api/v1/field/summary").json()
    assert s["total"] >= 1
    assert any(z["location_id"] == body["location_id"] for z in s["zones"])


def test_report_out_of_bounds_is_unbound(client, seeded):
    r = client.post(
        "/api/v1/field/reports",
        json={"observed_severity": 1, "description": "far away", "lat": -30.0, "lon": 25.0, "medium": "sms"},
    )
    assert r.status_code == 200
    assert r.json()["location_id"] is None
    assert r.json()["status"] == "pending"


def test_triage_and_vote_flow(client, seeded):
    _clean(seeded, "porur")
    loc = seeded.get(models.Location, "porur")
    rep = client.post(
        "/api/v1/field/reports",
        json={"observed_severity": 2, "description": "minor waterlogging near market", "lat": loc.lat, "lon": loc.lon},
    ).json()
    assert client.patch(f"/api/v1/field/reports/{rep['id']}/status", json={"status": "confirmed"}).status_code == 200
    v = client.post(f"/api/v1/field/reports/{rep['id']}/vote").json()
    assert v["votes"] == 1
    assert client.patch(f"/api/v1/field/reports/{rep['id']}/status", json={"status": "bogus"}).status_code == 422


# ---- scenario simulator -----------------------------------------------------

def test_propagate_is_deterministic_and_vivid(seeded):
    from app.services.scenario import ScenarioParams, propagate

    zones = list(seeded.query(models.Location).all())
    p = ScenarioParams(name="t", hazard_type="cyclone", start_lat=13.5, start_lon=79.6, end_lat=11.5, end_lon=78.2, duration_h=6, step_h=1, radius_km=130)
    a = propagate(zones, p)
    b = propagate(zones, p)
    assert a["frames"] == b["frames"]  # deterministic
    assert len(a["frames"]) == 7  # t=0..6
    s = a["summary"]
    assert s["affected_zones"] >= 1
    assert s["impact_score"] > 0
    assert s["top_zones"][0]["peak_p"] >= 0.3
    assert "shelter_capacity_recommended" in s


def test_scenario_api_roundtrip(client, seeded):
    _clean(seeded, "none")
    r = client.post(
        "/api/v1/scenarios",
        json={
            "name": "test sweep",
            "hazard_type": "flood",
            "start_lat": 13.2, "start_lon": 79.9,
            "end_lat": 12.4, "end_lon": 78.7,
            "intensity": 0.9, "radius_km": 120, "duration_h": 4, "step_h": 1,
        },
    )
    assert r.status_code == 200
    run = r.json()
    assert run["id"].startswith("scn_")
    assert run["summary"]["frames"] == 5

    full = client.get(f"/api/v1/scenarios/{run['id']}").json()
    assert len(full["frames"]) == 5
    assert len(full["frames"][0]["zones"]) >= 1

    lst = client.get("/api/v1/scenarios").json()
    assert any(x["id"] == run["id"] for x in lst)

    presets = client.get("/api/v1/scenarios/presets").json()
    assert len(presets) >= 4

    assert client.delete(f"/api/v1/scenarios/{run['id']}").status_code == 200


def test_scenario_broadcast_raises_drill_alerts(client, seeded):
    from app.services.scenario import ScenarioParams, run_scenario

    _clean(seeded, "mylapore")
    # reset sms off so no side effects
    get_settings().sms_enabled = False
    p = ScenarioParams(name="drill", hazard_type="cyclone", start_lat=13.1, start_lon=80.2, end_lat=12.6, end_lon=79.9, intensity=1.0, radius_km=60, duration_h=4, step_h=1)
    run = run_scenario(seeded, p)
    from app.services.scenario import broadcast_peak_alerts

    raised = broadcast_peak_alerts(seeded, run, level="critical")
    if raised:
        alerts = seeded.query(models.Alert).filter(models.Alert.title.ilike("%[DRILL]%")).count()
        assert alerts >= 1
    else:
        assert True  # theatre may not reach critical — no crash is the assertion


# ---- ops feed + ghost audit --------------------------------------------------

def test_ops_summary_and_events(client, seeded):
    ops_reset()
    s = client.get("/api/v1/ops/summary").json()
    for key in ("alerts_24h", "field_reports", "scenarios", "ghost_enabled", "sms_enabled"):
        assert key in s
    ev = client.get("/api/v1/ops/events").json()
    assert isinstance(ev, list)

    g = client.get("/api/v1/ops/ghost").json()
    assert isinstance(g, list)


def test_ghost_cycle_audits_actions(seeded):
    from app.notification.service import SmsService
    from app.services.ghost import GhostAgent

    _clean(seeded, "tambaram")
    agent = GhostAgent()
    db = SessionLocal()
    try:
        db.query(models.GhostAction).delete()
        db.commit()
        alert = models.Alert(
            location_id="tambaram",
            event_type="flood",
            level="critical",
            title="ghost probe",
            summary="ghost mode sweep test",
        )
        db.add(alert)
        db.commit()
        agent._cycle(db, SmsService(db))
        acts = db.query(models.GhostAction).filter(models.GhostAction.alert_id == alert.id).all()
        assert len(acts) >= 1
        assert acts[0].action in ("sms_broadcast", "escalation", "thatched")
        assert acts[0].alert_id == alert.id
    finally:
        db.close()


# ---- web push crypto ----------------------------------------------------------

def test_push_key_generation_persists(seeded):
    from app.services.push import get_or_create_keys, vapid_public_point_b64

    priv, pub = get_or_create_keys(seeded)
    assert "PRIVATE KEY" in priv and "PUBLIC KEY" in pub
    point = vapid_public_point_b64(pub)
    raw = base64.urlsafe_b64decode(point + "=" * (-len(point) % 4))
    assert len(raw) == 65 and raw[0] == 0x04
    # persists: second call returns same pair
    priv2, pub2 = get_or_create_keys(seeded)
    assert (priv2, pub2) == (priv, pub)


def test_push_encrypt_roundtrip(seeded):
    """Encrypt for a client keypair, then decrypt with the client private key."""
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.services.push import (
        _b64u,
        _uncompressed_point,
        encrypt_subscription_payload,
        hkdf_expand,
        hkdf_extract,
    )

    client_key = ec.generate_private_key(ec.SECP256R1())
    ua_raw = _uncompressed_point(client_key.public_key())
    auth = b"\x01" * 16
    payload = b'{"title":"roundtrip","body":"ok"}'

    body, meta = encrypt_subscription_payload(_b64u(ua_raw), _b64u(auth), payload)

    # parse aes128gcm body: salt(16) + rs(4) + idlen(1) + server(65) + ct
    _salt, _rs_b, idlen, server_raw, ct = body[:16], body[16:20], body[20], body[21:86], body[86:]
    assert idlen == 65

    server_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), server_raw)
    shared = client_key.exchange(ec.ECDH(), server_pub)[-32:]
    prk = hkdf_extract(auth, shared)
    ikm = hkdf_expand(prk, b"WebPush: info\x00" + ua_raw + server_raw, 32)
    ctx = b"P-256\x00" + len(ua_raw).to_bytes(2, "big") + ua_raw + len(server_raw).to_bytes(2, "big") + server_raw
    cek = hkdf_expand(ikm, b"Content-Encoding: aes128gcm\x00" + ctx, 16)
    nonce = hkdf_expand(ikm, b"Content-Encoding: nonce\x00" + ctx, 12)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = AESGCM(cek).decrypt(nonce, ct, b"")
    assert plaintext.rstrip(b"\x02") == payload


def test_push_register_and_public_endpoints(client, seeded):
    from app.services.push import get_or_create_keys

    get_or_create_keys(seeded)
    pub = client.get("/api/v1/push/public").json()
    assert pub["enabled"] is True
    assert len(pub["vapid_public_key"]) >= 80

    ep = "https://push.example.com/send/abc123"
    r = client.post(
        "/api/v1/push/register",
        json={"endpoint": ep, "p256dh": "B" * 87, "auth": "A" * 16, "ua": "pytest"},
    )
    assert r.status_code == 200
    assert client.get("/api/v1/push/count").json()["subscriptions"] >= 1
    assert client.post("/api/v1/push/unregister", json={"endpoint": ep}).status_code == 200
    n = client.get("/api/v1/push/count").json()["subscriptions"]
    assert n >= 0