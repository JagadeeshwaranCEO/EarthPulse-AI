"""Crossing-time projection — when will the high band actually hit?

Turns the forecast curve and driver trajectories into clock answers:
"high-band risk in ~9h", "rain intensity crosses its stress line in ~5h".
Honest framing: projections are trend-extrapolations of the fused components
and the forecaster's damped outlook — "if the current trajectory holds",
stated on every response.

Risk crossing: first hour where the forecast mean pierces the hazard's high
threshold (or moderate, if high is unreachable in the window).
Driver crossing: per fused component, Brown-smoothed trajectory extrapolated
with a damped trend until it pierces the stress line (60% of the 0-12 scale,
the point where the driver stops being background and starts dominating).
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.core.models import Location
from app.ml.forecaster import DEFAULT_FORECASTER
from app.services.risk_evolution import evolution

STRESS_FRACTION = 0.6  # of the 0-12 component scale
LOOKBACK_DRIVERS = 24
EXTRAPOLATE_H = 72
TREND_DECAY = 0.035


def _extrapolate_crossing(series: list[float], stress_line: float) -> int | None:
    x = np.asarray(series[-LOOKBACK_DRIVERS:], dtype=float)
    if len(x) < 3:
        return None
    smoothed = DEFAULT_FORECASTER._smooth(x)
    level, trend = smoothed[-1], (smoothed[-1] - smoothed[-2])
    if level >= stress_line:
        return 0  # already stressed
    for h in range(1, EXTRAPOLATE_H + 1):
        damp = np.exp(-TREND_DECAY * h)
        if level + trend * h * damp >= stress_line:
            return int(h)
    return None


def project_crossing(db, loc: Location) -> dict:
    from app.agents.orchestrator import build_agent_outputs
    from app.hazards.registry import get_hazard

    hazard = get_hazard(loc.hazard_type)
    ev = evolution(db, loc, lookback_h=48, horizon_h=24)
    outputs, _ = build_agent_outputs(db, loc.id)
    pred = outputs.get("prediction") or {}
    fc = pred.get("forecast_series")
    confidence = pred.get("confidence", 0.0)
    now_hour = ev["now_hour"]

    thresholds = hazard.thresholds
    high_cut = thresholds.get("high", 0.6)
    mod_cut = thresholds.get("moderate", 0.35)

    risk_high = None
    risk_moderate = None
    if fc is not None:
        for h, m in enumerate(fc.mean, start=1):
            if risk_high is None and m >= high_cut:
                risk_high = h
            if risk_moderate is None and m >= mod_cut:
                risk_moderate = h
            if risk_high is not None and risk_moderate is not None:
                break

    now_points = [p for p in ev["points"] if p["is_now"]]
    now_comps = now_points[0]["components"] if now_points else {}

    drivers = []
    for feature, label in hazard.features.items():
        series = []
        for p in ev["points"]:
            if p["hour"] <= now_hour and feature in p["components"]:
                series.append(float(p["components"][feature]))
        if len(series) < 3:
            continue
        crossing_h = _extrapolate_crossing(series, STRESS_FRACTION * 12.0)
        drivers.append(
            {
                "driver": feature,
                "label": label,
                "current": round(now_comps.get(feature, 0.0), 2),
                "stress_line": round(STRESS_FRACTION * 12.0, 1),
                "crosses_stress_in_h": crossing_h,  # 0 = already stressed; None = not in 72h
            }
        )
    drivers.sort(key=lambda d: 1e9 if d["crosses_stress_in_h"] is None else d["crosses_stress_in_h"])

    return {
        "location_id": loc.id,
        "hazard": hazard.id,
        "now_hour": now_hour,
        "high_band": {"threshold": high_cut, "crossing_in_h": risk_high},
        "moderate_band": {"threshold": mod_cut, "crossing_in_h": risk_moderate},
        "drivers": drivers,
        "confidence": round(confidence, 3),
        "method": "trend extrapolation of fused components + forecast curve — if the current trajectory holds",
        "generated_at": datetime.now(timezone.utc),
    }
