"""Ghost Mode — the autonomous escalation agent.

A watchdog thread (started from the app lifespan) that watches unresolved
alerts and acts on them without a human in the loop: it broadcasts SMS to
anyone subscribed to the affected zone(s), audits every action, and pushes a
live event to the ops feed. Safe to re-run: delivery records + the SmsMessage
fence dact as dedup, so nothing is double-sent.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core import models
from app.core.db import SessionLocal

if TYPE_CHECKING:
    from app.notification.service import SmsService

log = logging.getLogger("earthpulse.ghost")

_LEVEL_RANK = {"advisory": 1, "watch": 2, "warning": 3, "critical": 4}


class GhostAgent(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="ghost-agent", daemon=True)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        from app.config import get_settings
        from app.notification.service import SmsService

        log.info("ghost agent online")
        while not self._stop.wait(get_settings().ghost_check_seconds):
            if not get_settings().ghost_enabled:
                continue
            db = SessionLocal()
            try:
                self._cycle(db, SmsService(db))
            except Exception:
                log.exception("ghost cycle failed")
            finally:
                db.close()
        log.info("ghost agent offline")

    def _cycle(self, db, sms: SmsService) -> None:
        from app.config import get_settings
        from app.core import models as cm
        from app.core.ops import publish

        settings = get_settings()
        min_rank = _LEVEL_RANK.get(settings.ghost_broadcast_min_level, 3)

        acted: set[int] = set(row.alert_id for row in db.query(models.GhostAction).all() if row.alert_id)
        alerts = (
            db.query(cm.Alert)
            .filter(cm.Alert.resolved == False)  # noqa: E712
            .order_by(cm.Alert.raised_at.asc())
            .limit(settings.ghost_broadcast_max_per_cycle)
            .all()
        )

        for alert in alerts:
            if alert.id in acted:
                continue
            level_rank = _LEVEL_RANK.get(alert.level, 0)
            if level_rank < min_rank:
                continue

            verb, detail, recipients = "sms_broadcast", "", 0
            if settings.sms_enabled:
                sent = sms.process_alert(alert)
                recipients = self._subscribers_count(db, alert.location_id)
                verb = "sms_broadcast" if sent > 0 else "thatched"
                detail = f"zone {alert.location_id} · level {alert.level} · sms delivered {sent}/{recipients}"
            else:
                verb, detail = "escalation", f"zone {alert.location_id} · level {alert.level} · no SMS carrier"

            db.add(
                models.GhostAction(
                    alert_id=alert.id,
                    action=verb,
                    detail=detail,
                    recipients=recipients,
                )
            )
            db.commit()

            try:
                publish(
                    {
                        "type": "ghost",
                        "action": verb,
                        "alert_id": alert.id,
                        "zone": alert.location_id,
                        "level": alert.level,
                        "title": alert.title,
                        "recipients": recipients,
                        "at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            except Exception:
                log.warning("ghost ws publish failed", exc_info=True)

        log.info("ghost sweep: %d alerts evaluated", len(alerts))

    @staticmethod
    def _subscribers_count(db, location_id: str) -> int:
        from app.notification import models as sm

        return db.query(sm.SmsSubscription).filter(sm.SmsSubscription.location_id == location_id).count()