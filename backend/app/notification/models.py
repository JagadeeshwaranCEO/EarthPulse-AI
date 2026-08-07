"""SMS notification entities — recipients, subscriptions, messages, attempts, audit.

The notification domain is deliberately separate from the prediction domain so
the two stay independently evolvable: the pipeline writes `Alert` rows, the
notification layer reads them and tracks everything SMS-related here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SmsRecipient(Base):
    __tablename__ = "sms_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # E.164, e.g. +919876543210
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Severity floor: "critical" | "warning" | "watch" | "advisory" — user picks how loud alerts get.
    min_level: Mapped[str] = mapped_column(String(16), default="warning")
    quiet_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SmsSubscription(Base):
    __tablename__ = "sms_subscriptions"
    __table_args__ = (UniqueConstraint("recipient_id", "location_id", name="uq_sms_sub_recipient_location"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("sms_recipients.id"), index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SmsMessage(Base):
    __tablename__ = "sms_messages"
    __table_args__ = (Index("ix_sms_msg_event", "location_id", "event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("sms_recipients.id"), index=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # alert id that triggered this SMS
    kind: Mapped[str] = mapped_column(String(16), default="alert")  # alert | test | otp | broadcast
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)  # queued|sent|delivered|failed|suppressed
    provider: Mapped[str] = mapped_column(String(32), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    risk_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SmsDeliveryAttempt(Base):
    __tablename__ = "sms_delivery_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("sms_messages.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(32))
    provider_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SmsOtp(Base):
    __tablename__ = "sms_otps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))  # sha256 of the OTP — never store plaintext
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SmsAuditLog(Base):
    __tablename__ = "sms_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)  # register|verify|subscribe|unsubscribe|settings|test|send|failover|suppress
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
