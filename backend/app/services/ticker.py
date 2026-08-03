"""Demo simulation clock — the time-scrubbing digital twin's engine.

The seed dataset covers 72 hours ending at the storm peak. The clock starts at
hour 62 (pre-peak) and advances 1h per WS tick, so a live demo escalates through
the peak into crisis mode, then eases. REST reads are stateless; only the WS
broadcaster (or an explicit clock set) advances time.
"""

import threading

_START_HOUR = 48.0
_MAX_HOUR = 80.0

_lock = threading.Lock()
_state = {"hour": _START_HOUR, "step": 1.0, "anchor_iso": None}


def set_anchor(anchor_iso: str) -> None:
    with _lock:
        _state["anchor_iso"] = anchor_iso


def get_anchor() -> str | None:
    with _lock:
        return _state["anchor_iso"]


def current_hour() -> float:
    with _lock:
        return _state["hour"]


def advance() -> float:
    with _lock:
        _state["hour"] = min(_MAX_HOUR, _state["hour"] + _state["step"])
        return _state["hour"]


def set_hour(hour: float) -> float:
    with _lock:
        _state["hour"] = max(0.0, min(_MAX_HOUR, hour))
        return _state["hour"]


def get_state() -> dict:
    return {"hour": current_hour(), "max": _MAX_HOUR, "step": _state["step"]}


def reset() -> None:
    with _lock:
        _state["hour"] = _START_HOUR
