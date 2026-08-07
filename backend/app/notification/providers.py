"""SMS provider abstraction — the notification service only knows this interface.

Each provider implementation turns a (to, body, sender_id) into an HTTP call
against its vendor API. Adding a new carrier is: subclass `SmsProvider`,
register it in `PROVIDERS`, set `SMS_PROVIDER` in env. Business logic never
imports a vendor SDK.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger("earthpulse.sms")


@dataclass
class SendResult:
    ok: bool
    provider_ref: str | None = None
    error: str | None = None
    details: dict = field(default_factory=dict)


class SmsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        """Deliver one SMS; must never raise — return a SendResult instead."""

    def health(self, timeout_s: float = 5.0) -> bool:
        """Cheap connectivity probe. Default: config present (subclasses may ping)."""
        return True


def _post_form(url: str, fields: dict, headers: dict | None = None, timeout_s: float = 10.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # network/timeout — provider may be down
        return 0, str(e)


class LogProvider(SmsProvider):
    """Default dev provider — prints the message, never hits the network."""

    name = "log"

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        log.info("SMS [%s] to=%s sender=%s\n%s", self.name, to, sender_id, body)
        return SendResult(ok=True, provider_ref=f"log:{to}", details={"preview": body})


class TwilioProvider(SmsProvider):
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        basic = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        fields = {"To": to, "From": self.from_number, "Body": body}
        code, raw = _post_form(url, fields, {"Authorization": f"Basic {basic}"}, timeout_s)
        if code in (200, 201):
            sid = ""
            for part in raw.split("&"):
                if part.startswith("sid="):
                    sid = urllib.parse.unquote(part[4:])
                    break
            return SendResult(ok=True, provider_ref=sid or "twilio:ok")
        return SendResult(ok=False, error=f"twilio http {code}: {raw[:200]}")


class MessageBirdProvider(SmsProvider):
    name = "messagebird"

    def __init__(self, api_key: str, originator: str):
        self.api_key = api_key
        self.originator = originator

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = "https://rest.messagebird.com/messages"
        fields = {"originator": self.originator or sender_id, "recipients": to, "body": body}
        code, raw = _post_form(url, fields, {"Authorization": f"AccessKey {self.api_key}"}, timeout_s)
        if code in (200, 201):
            return SendResult(ok=True, provider_ref=f"messagebird:{code}")
        return SendResult(ok=False, error=f"messagebird http {code}: {raw[:200]}")


class VonageProvider(SmsProvider):
    name = "vonage"

    def __init__(self, api_key: str, api_secret: str, from_number: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.from_number = from_number

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = "https://rest.nexmo.com/sms/json"
        fields = {"api_key": self.api_key, "api_secret": self.api_secret, "from": self.from_number or sender_id, "to": to, "text": body}
        code, raw = _post_form(url, fields, timeout_s=timeout_s)
        if code == 200 and '"messages"' in raw:
            return SendResult(ok=True, provider_ref=f"vonage:{code}")
        return SendResult(ok=False, error=f"vonage http {code}: {raw[:200]}")


class TextlocalProvider(SmsProvider):
    name = "textlocal"

    def __init__(self, api_key: str, sender: str):
        self.api_key = api_key
        self.sender = sender

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = "https://api.textlocal.in/send/"
        fields = {"apikey": self.api_key, "sender": self.sender or sender_id, "numbers": to, "message": body}
        code, raw = _post_form(url, fields, timeout_s=timeout_s)
        if code == 200 and '"status":"success"' in raw:
            return SendResult(ok=True, provider_ref=f"textlocal:{code}")
        return SendResult(ok=False, error=f"textlocal http {code}: {raw[:200]}")


class Msg91Provider(SmsProvider):
    name = "msg91"

    def __init__(self, auth_key: str, sender_id: str, route: int = 4):
        self.auth_key = auth_key
        self.sender_id = sender_id
        self.route = route

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = "https://api.msg91.com/api/v2/sendsms"
        fields = {"authkey": self.auth_key, "mobiles": to.lstrip("+"), "message": body, "sender": self.sender_id or sender_id, "route": self.route, "unicode": 0}
        code, raw = _post_form(url, fields, timeout_s=timeout_s)
        if code == 200 and '"type":"success"' in raw:
            return SendResult(ok=True, provider_ref=f"msg91:{code}")
        return SendResult(ok=False, error=f"msg91 http {code}: {raw[:200]}")


class AwsSnsProvider(SmsProvider):
    """AWS SNS Publish with SigV4 — no boto3 dependency."""

    name = "aws_sns"

    def __init__(self, access_key: str, secret_key: str, region: str, session_token: str = ""):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.session_token = session_token

    def _sign(self, payload: bytes, amz_date: str) -> str:
        host = f"sns.{self.region}.amazonaws.com"
        canonical = (
            "POST\n/\n\n"
            f"content-type:application/x-www-form-urlencoded; charset=utf-8\nhost:{host}\n"
            f"x-amz-date:{amz_date}\n\n"
            "content-type;host;x-amz-date\n"
            + hashlib.sha256(payload).hexdigest()
        )
        k_date = hmac.new(("AWS4" + self.secret_key).encode(), amz_date[:8].encode(), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self.region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, b"sns", hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
        signature = hmac.new(k_signing, (f"AWS4-HMAC-SHA256\n{amz_date}\n{amz_date[:8]}/{self.region}/sns/aws4_request\n" + hashlib.sha256(canonical.encode()).hexdigest()).encode(), hashlib.sha256).hexdigest()
        return (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{amz_date[:8]}/{self.region}/sns/aws4_request, "
            f"SignedHeaders=content-type;host;x-amz-date, Signature={signature}"
        )

    def send(self, to: str, body: str, sender_id: str, timeout_s: float = 10.0) -> SendResult:
        url = f"https://sns.{self.region}.amazonaws.com/"
        payload = urllib.parse.urlencode(
            {
                "Action": "Publish",
                "Message": body,
                "PhoneNumber": to,
                "Version": "2010-03-31",
            }
        ).encode()
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "X-Amz-Date": amz_date,
            "Authorization": self._sign(payload, amz_date),
        }
        if self.session_token:
            headers["X-Amz-Security-Token"] = self.session_token
        try:
            req = urllib.request.Request(url, data=payload, method="POST")
            for k, v in headers.items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return SendResult(ok=True, provider_ref=f"sns:{resp.status}")
        except urllib.error.HTTPError as e:
            return SendResult(ok=False, error=f"sns http {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        except Exception as e:
            return SendResult(ok=False, error=f"sns: {e}")


PROVIDERS: dict[str, type[SmsProvider]] = {
    "log": LogProvider,
    "twilio": TwilioProvider,
    "messagebird": MessageBirdProvider,
    "vonage": VonageProvider,
    "textlocal": TextlocalProvider,
    "msg91": Msg91Provider,
    "aws_sns": AwsSnsProvider,
}


def build_provider(name: str, settings) -> SmsProvider | None:
    """Instantiate a provider from settings. Returns None if the provider's
    credentials are missing (so failover can skip it)."""
    if name == "log":
        return LogProvider()
    if name == "twilio":
        if not (settings.sms_twilio_account_sid and settings.sms_twilio_auth_token and settings.sms_twilio_from):
            return None
        return TwilioProvider(settings.sms_twilio_account_sid, settings.sms_twilio_auth_token, settings.sms_twilio_from)
    if name == "messagebird":
        return MessageBirdProvider(settings.sms_messagebird_api_key, settings.sms_messagebird_originator) if settings.sms_messagebird_api_key else None
    if name == "vonage":
        return VonageProvider(settings.sms_vonage_api_key, settings.sms_vonage_api_secret, settings.sms_vonage_from) if (settings.sms_vonage_api_key and settings.sms_vonage_api_secret) else None
    if name == "textlocal":
        return TextlocalProvider(settings.sms_textlocal_api_key, settings.sms_textlocal_sender) if settings.sms_textlocal_api_key else None
    if name == "msg91":
        return Msg91Provider(settings.sms_msg91_auth_key, settings.sms_msg91_sender) if settings.sms_msg91_auth_key else None
    if name == "aws_sns":
        if not (settings.sms_aws_access_key and settings.sms_aws_secret_key):
            return None
        return AwsSnsProvider(settings.sms_aws_access_key, settings.sms_aws_secret_key, settings.sms_aws_region, settings.sms_aws_session_token or "")
    return None
