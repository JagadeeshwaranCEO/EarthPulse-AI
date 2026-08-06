"""WebSocket — live mission-control tick.

Pushes {type: tick, time, pulse, crisis, alerts, top_risks} every TICK_SECONDS so
the demo feels alive without manual refresh. REST fallback exists in the UI.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.ticker import advance

router = APIRouter(tags=["ws"])

connections: set[WebSocket] = set()


def _payload() -> dict:
    from app.api.routes.dashboard import get_dashboard
    from app.core.db import SessionLocal

    db = None
    try:
        db = SessionLocal()
        dash = get_dashboard(db)
        dumped = dash.model_dump(mode="json")
        return {
            "type": "tick",
            "time": datetime.now(timezone.utc).isoformat(),
            "pulse": dumped["pulse"],
            "crisis": dumped["crisis"],
            "alerts": dumped["alerts"],
            "top_risks": dumped["risks"][:6],
            "tick_seconds": dumped["tick_seconds"],
        }
    except Exception as exc:  # seed not ready / engine disposed during teardown
        logging.getLogger("earthpulse.ws").warning("tick payload failed: %s", exc, exc_info=True)
        return {"type": "tick", "time": datetime.now(timezone.utc).isoformat(), "error": str(exc)}
    finally:
        if db is not None:
            db.close()


async def broadcaster() -> None:
    while True:
        await asyncio.sleep(get_settings().tick_seconds)
        if not connections:
            continue
        advance()  # sim clock: +1h per tick → live escalation through storm peak
        data = _payload()
        dead = []
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                logging.getLogger("earthpulse.ws").warning("websocket send failed — dropping connection", exc_info=True)
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connections.add(ws)
    try:
        await ws.send_json(_payload())
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        connections.discard(ws)
