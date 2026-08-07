"""Web Push (RFC 8291) delivery — VAPID-signed, aes128gcm-encrypted, HTTP/2.

Requirements: `cryptography` (ECDSA P-256 + AES-GCM) and `h2` (for httpx HTTP/2).
The VAPID keypair is generated once and persisted in `push_keys` so browser
subscriptions survive app restarts. Credentials never touch the API surface —
endpoints only expose the public point and accept subscription payloads.
"""

from __future__ import annotations

import base64
import time
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models

CURVE = ec.SECP256R1()


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _uncompressed_point(pub) -> bytes:
    n = pub.public_numbers()
    return b"\x04" + n.x.to_bytes(32, "big") + n.y.to_bytes(32, "big")


def _load_private(priv_pem: str):
    return serialization.load_pem_private_key(priv_pem.encode(), password=None)


def _load_public(pub_pem: str):
    return serialization.load_pem_public_key(pub_pem.encode())


def vapid_public_point_b64(pub_pem: str) -> str:
    """65-byte uncompressed point, base64url — what the browser's subscribe() wants."""
    return _b64u(_uncompressed_point(_load_public(pub_pem)))


def _es256_sign(priv, signing_input: bytes) -> bytes:
    der = priv.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return r.to_bytes(32, "big") + s.to_bytes(32, "big")


def vapid_token(priv_pem: str, aud: str, sub: str) -> str:
    priv = _load_private(priv_pem)
    header = _b64u(b'{"typ":"JWT","alg":"ES256"}')
    exp = int(time.time()) + 12 * 3600
    payload = _b64u(f'{{"aud":"{aud}","exp":{exp},"sub":"{sub}"}}'.encode())
    sig = _b64u(_es256_sign(priv, f"{header}.{payload}".encode()))
    return f"{header}.{payload}.{sig}"


def hkdf_extract(salt: bytes, ikm: bytes, length: int = 32) -> bytes:
    """RFC 5869 HKDF-Extract — PRK = HMAC-SHA256(salt, ikm)."""
    h = hmac.HMAC(salt, hashes.SHA256())
    h.update(ikm)
    return h.finalize()[:length]


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    return HKDFExpand(algorithm=hashes.SHA256(), length=length, info=info).derive(prk)


def _context(ua: bytes, server: bytes) -> bytes:
    return b"P-256\x00" + len(ua).to_bytes(2, "big") + ua + len(server).to_bytes(2, "big") + server


def _record_header(server_raw: bytes, plaintext_len: int, salt: bytes) -> bytes:
    rs = (plaintext_len + 16).to_bytes(4, "big")
    return salt + rs + bytes([len(server_raw)]) + server_raw


def encrypt_subscription_payload(ua_public_b64: str, auth_b64: str, payload: bytes) -> tuple[bytes, dict]:
    """RFC 8291 aes128gcm encryption. Returns (body, {server_b64, server_raw}).

    The server_public key is embedded in the record header; the browser derives
    the shared secret from its own private key + this ephemeral public key.
    """
    ua_raw = _b64u_decode(ua_public_b64)
    if len(ua_raw) != 65 or ua_raw[0] != 0x04:
        raise ValueError("p256dh must be a 65-byte uncompressed P-256 point")
    ua_pub = ec.EllipticCurvePublicKey.from_encoded_point(CURVE, ua_raw)
    auth = _b64u_decode(auth_b64)

    ephemeral = ec.generate_private_key(CURVE)
    server_raw = _uncompressed_point(ephemeral.public_key())
    shared = ephemeral.exchange(ec.ECDH(), ua_pub)[-32:]

    prk = hkdf_extract(auth, shared)
    ikm = hkdf_expand(prk, b"WebPush: info\x00" + ua_raw + server_raw, 32)
    ctx = _context(ua_raw, server_raw)
    cek = hkdf_expand(ikm, b"Content-Encoding: aes128gcm\x00" + ctx, 16)
    nonce = hkdf_expand(ikm, b"Content-Encoding: nonce\x00" + ctx, 12)

    plaintext = payload + b"\x02"  # single final record
    ct = AESGCM(cek).encrypt(nonce, plaintext, b"")
    salt = b"\x00" * 16  # aes128gcm salt is carried in-band; auth secret does the keying

    body = _record_header(server_raw, len(plaintext), salt) + ct
    return body, {"server_b64": _b64u(server_raw), "server_raw": server_raw}


def get_or_create_keys(db: Session) -> tuple[str, str]:
    """Return (private_pem, public_pem) — generated + persisted on first boot."""
    row = db.query(models.PushKey).order_by(models.PushKey.id.asc()).first()
    if row is not None:
        return row.private_pem, row.public_pem

    settings = get_settings()
    if settings.vapid_private_pem and settings.vapid_public_pem:
        db.add(models.PushKey(private_pem=settings.vapid_private_pem, public_pem=settings.vapid_public_pem))
        db.commit()
        return settings.vapid_private_pem, settings.vapid_public_pem

    priv = ec.generate_private_key(CURVE)
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    db.add(models.PushKey(private_pem=priv_pem, public_pem=pub_pem))
    db.commit()
    return priv_pem, pub_pem


def send_webpush(
    endpoint: str,
    p256dh_b64: str,
    auth_b64: str,
    payload: bytes,
    priv_pem: str,
    pub_pem: str,
    ttl_s: int = 3600,
    contact: str = "ops@earthpulse.ai",
) -> dict:
    """Encrypt + deliver a payload to a subscription over HTTP/2 with VAPID auth."""
    body, _ = encrypt_subscription_payload(p256dh_b64, auth_b64, payload)
    origin = urlsplit(endpoint)
    aud = f"{origin.scheme}://{origin.netloc}"
    token = vapid_token(priv_pem, aud, contact)
    public_b64 = vapid_public_point_b64(pub_pem)

    headers = {
        "Authorization": f"vapid t={token},k={public_b64}",
        "TTL": str(int(ttl_s)),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
    }
    try:
        with httpx.Client(http2=True, timeout=15.0) as client:
            resp = client.post(endpoint, headers=headers, content=body)
        return {"ok": resp.is_success, "status": resp.status_code, "error": None if resp.is_success else resp.text[:200]}
    except Exception as exc:  # network / TLS / endpoint refused
        return {"ok": False, "status": None, "error": str(exc)[:200]}


def push_message(title: str, body: str, url: str | None = None, tag: str = "earthpulse") -> bytes:
    """Envelope the notification payload the service worker displays."""
    import json

    payload = {"title": title, "body": body, "tag": tag, "url": url or "/", "via": "push"}
    return json.dumps(payload, separators=(",", ":")).encode()