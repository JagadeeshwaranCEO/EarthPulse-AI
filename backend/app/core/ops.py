"""Ops bus — a tiny thread-safe pub/sub for the live ops feed.

Sync handlers publish events into a deque; the WS broadcaster drains them into
the tick stream so the whole mission-control surface stays alive without a
poll loop. REST fallback (`ops.summary` / `ops.events`) mirrors the same source
of truth for the panels that are not connected to WS.
"""

from __future__ import annotations

import collections
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

_EVENTS: collections.deque[dict] = collections.deque(maxlen=200)
_LOCK = threading.Lock()


def publish(event: dict) -> None:
    """Enqueue an event for the WS stream. Never raises."""
    with _LOCK:
        _EVENTS.append({"at": datetime.now(timezone.utc).isoformat(), **event})


def drain() -> list[dict]:
    with _LOCK:
        out = list(_EVENTS)
        _EVENTS.clear()
    return out


def reset() -> None:
    """Test hook — clear the local event queue (mirrors ticker.reset())."""
    with _LOCK:
        _EVENTS.clear()


def recent(db: Session, limit: int = 50) -> list[dict]:
    """REST fallback: merge recent activity from every ops source, desc."""
    from app.core import models

    events: list[dict] = []

    for a in db.query(models.Alert).order_by(models.Alert.raised_at.desc()).limit(10).all():
        events.append(
            {
                "kind": "alert",
                "at": a.raised_at.isoformat(),
                "zone": a.location_id,
                "level": a.level,
                "detail": a.title,
            }
        )
    for r in db.query(models.FieldReport).order_by(models.FieldReport.created_at.desc()).limit(10).all():
        events.append(
            {
                "kind": "field_report",
                "at": r.created_at.isoformat(),
                "zone": r.location_id or "unbound",
                "level": "confirmed" if r.status == "confirmed" else r.status,
                "detail": f"severity {r.observed_severity}/5 — {r.description[:90]}",
            }
        )
    for s in db.query(models.ScenarioRun).order_by(models.ScenarioRun.created_at.desc()).limit(6).all():
        events.append(
            {
                "kind": "scenario",
                "at": s.created_at.isoformat(),
                "zone": f"{s.hazard_type} theatre",
                "level": "drill",
                "detail": f"{s.name} · impact {s.summary.get('impact_score', 0)}",
            }
        )
    from app.notification import models as sm

    for m in db.query(sm.SmsMessage).order_by(sm.SmsMessage.created_at.desc()).limit(10).all():
        events.append(
            {
                "kind": "sms",
                "at": m.created_at.isoformat(),
                "zone": m.location_id or "—",
                "level": m.status,
                "detail": f"{m.kind} · {m.provider or 'log'}",
            }
        )
    for g in db.query(models.GhostAction).order_by(models.GhostAction.created_at.desc()).limit(10).all():
        events.append(
            {
                "kind": "ghost",
                "at": g.created_at.isoformat(),
                "zone": g.detail.split("·")[0].strip()[:24],
                "level": g.action,
                "detail": g.detail,
            }
        )

    events.sort(key=lambda e: e["at"], reverse=True)
    return events[: limit]


def ops_summary(db: Session) -> dict:
    """Aircraft-style heads-up numbers for the Live Ops panel."""
    from datetime import timedelta

    from app.config import get_settings
    from app.core import models
    from app.notification import models as sm

    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    def last_day(model, col) -> int:
        return db.query(model).filter(col >= day_ago).count()

    return {
        "theatre": get_settings().scope,
        "ghost_enabled": get_settings().ghost_enabled,
        "sms_enabled": get_settings().sms_enabled,
        "push_enabled": get_settings().push_enabled,
        "alerts_24h": last_day(models.Alert, models.Alert.raised_at),
        "active_alerts": db.query(models.Alert).filter(models.Alert.resolved == False).count(),  # noqa: E712
        "field_reports": db.query(models.FieldReport).count(),
        "field_confirmed": db.query(models.FieldReport).filter(models.FieldReport.status == "confirmed").count(),
        "field_pending": db.query(models.FieldReport).filter(models.FieldReport.status == "pending").count(),
        "scenarios": db.query(models.ScenarioRun).count(),
        "ghost_actions": db.query(models.GhostAction).count(),
        "sms_recipients": db.query(sm.SmsRecipient).count(),
        "sms_messages": db.query(sm.SmsMessage).count(),
        "sms_sent": db.query(sm.SmsMessage).filter(sm.SmsMessage.status == "sent").count(),
    }