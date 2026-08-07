"""Emergency event listener — bridge between the pipeline and SMS delivery.

`refresh_predictions` persists `Alert` rows; `scan_new_alerts` finds alerts the
notification layer hasn't seen yet and hands them to the SMS service. The
pipeline stays untouched — it never imports a provider.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models as core_models
from app.notification.models import SmsMessage
from app.notification.service import SmsService, naive_utc

log = logging.getLogger("earthpulse.sms")


def scan_new_alerts(db: Session, since_minutes: int = 10) -> int:
    """Deliver SMS for alerts raised in the last window that have no SMS yet.

    Returns the number of SMS messages sent. Safe to call repeatedly — the
    delivery records act as the dedup fence.
    """
    if not get_settings().sms_enabled:
        return 0

    since = naive_utc() - timedelta(minutes=since_minutes)
    alerts = db.scalars(
        select(core_models.Alert)
        .where(core_models.Alert.raised_at >= since, core_models.Alert.resolved == False)  # noqa: E712
        .order_by(core_models.Alert.raised_at.asc())
    ).all()

    service = SmsService(db)
    sent = 0
    for alert in alerts:
        already = db.scalar(
            select(SmsMessage).where(SmsMessage.event_id == alert.id, SmsMessage.kind == "alert").limit(1)
        )
        if already is not None:
            continue
        try:
            sent += service.process_alert(alert)
        except Exception:
            log.exception("SMS processing failed for alert %s", alert.id)
    return sent
