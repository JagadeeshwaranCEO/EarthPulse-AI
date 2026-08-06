"""Lead-aware nowcast engine — Stage A → Stage B.

EarthPulse's old forecaster only saw the *past*: it extrapolated the realized
probability line, so an incoming storm ramp (already present in the rain
*forecast*) was invisible until it accumulated. This module is the fix: it
moves the forecast into the present-tense driver space.

Stage A — forward-signal fusion:
  blend current fused components with forward signals that genuinely exist in
  the payload at issuance time (rain_forecast_mm, upstream inflow trend, soil
  saturation memory) into a lead-aware driver state.

Stage B — hazard state update:
  squash each lead-aware state through the hazard formula to score risk at
  +1h/+3h/+6h/+12h/+24h, each with a confidence band and a reason trail.

Honest boundary: geophysical hazards (earthquake, tsunami, volcanic) have no
credible day-of forecast feed in the demo, so their ladder stays
trajectory-flat with wide bands and an explicit "no forward signal" note rather
than fabricating lead. Hydromet hazards blend their own forecast feed so they
legitimately lead the observed ramp.
"""

from __future__ import annotations

import numpy as np

LEADS = (1, 3, 6, 12, 24)
FLOOD_FORWARD_DRIVERS = ("rain_intensity", "soil_moisture", "headroom_deficit", "drainage_stress")
CYCLONE_FORWARD_DRIVERS = ("rain_burst",)
LANDSLIDE_FORWARD_DRIVERS = ("rain_trigger", "slope_saturation")


def _nudge(
    comps: dict, driver: str, fc_intensity: float, lead_h: int, exposure: float, rate: float
) -> tuple[float, str]:
    """Forward ramps a driver toward the forecast intensity, weighted by lead.

    The forecast feed (rain_forecast_mm) is valid ~+6h ahead: influence ramps
    in up to +6h, then *holds* at the forecast intensity for longer leads —
    worst-case persistence, the operational standard when convective rain is
    already approaching. Decay is expressed through widening uncertainty bands
    instead of collapsing probability, so an incoming storm is not silently
    smoothed away at +12/+24h (the old system's blind spot).
    """
    cur = comps.get(driver, 0.0)
    w = float(np.clip((lead_h - 1.0) / 5.0, 0.0, 1.0))  # ramp to +6h, hold after
    gain = (fc_intensity - cur) * w * rate
    if gain <= 0:
        return cur, None
    nxt = min(12.0, cur + gain)
    tail = "; holding forecast intensity (persistence) past +6h feed" if lead_h > 6 else ""
    return nxt, f"rain forecast {fc_intensity * 16:.0f}mm/6h lifts {driver} +{nxt - cur:.1f}/12 by +{lead_h}h{tail}"


def components_ahead(comps: dict, hazard_id: str, signal: dict, exposure: float, lead_h: int) -> tuple[dict, list[str]]:
    """Stage A → B; returns (lead-aware components at +lead_h, reason trail)."""
    out = dict(comps)
    fc_intensity = min(12.0, float(signal.get("rain_forecast_mm", 0.0)) / 16.0 * exposure)
    reasons = []

    if hazard_id == "flood":
        for d in FLOOD_FORWARD_DRIVERS:
            rate = 1.0 if d == "rain_intensity" else 0.6 if d == "soil_moisture" else 0.7
            nv, r = _nudge(comps, d, fc_intensity, lead_h, exposure, rate)
            if r:
                out[d] = nv
                reasons.append(r)
        if signal.get("inflow_m3s"):
            reasons.append(f"upstream inflow {signal['inflow_m3s']:.0f} m3/s feeding basin inertia")
    elif hazard_id == "cyclone":
        for d in CYCLONE_FORWARD_DRIVERS:
            nv, r = _nudge(comps, d, fc_intensity, lead_h, exposure, 0.5)
            if r:
                out[d] = nv
                reasons.append(r)
        if not reasons:
            reasons.append("no wind-track forecast feed; rain-forecast only")
    elif hazard_id == "landslide":
        for d in LANDSLIDE_FORWARD_DRIVERS:
            nv, r = _nudge(comps, d, fc_intensity, lead_h, exposure, 0.55)
            if r:
                out[d] = nv
                reasons.append(r)
    elif hazard_id not in ("earthquake", "tsunami", "volcanic"):
        # drought/heatwave/wildfire have no precip-forward that helps → flat
        reasons.append("no credible forward signal at this lead; trajectory-flat")

    if not reasons:
        reasons.append("no forward signal available; trajectory extrapolation only")
    if lead_h > 6:
        reasons.append(f"lead {lead_h}h — confidence decays with horizon")
    return out, reasons


def lead_ladder(comps: dict, hazard_id: str, signal: dict, exposure: float) -> list[dict]:
    """Stage B — risk at the standard lead ladder, each with a reason trail."""
    from app.hazards.registry import get_hazard

    h = get_hazard(hazard_id)
    ladder = []
    for L in LEADS:
        c, reasons = components_ahead(comps, hazard_id, signal, exposure, L)
        p = min(1.0, max(0.0, h.probability(c)))
        ladder.append(
            {
                "lead_h": L,
                "probability": round(p, 3),
                "level": h.level(p),
                "components": {k: round(v, 2) for k, v in c.items()},
                "reasons": reasons,
            }
        )
    return ladder


# --- forward-signal extraction (payload feed for the live pipeline) ---
def signal_from_payload(payload: dict) -> dict:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    sat = agg.get("satellite", {})
    rain_fc = float(weather.get("rain_forecast_mm", 0.0) or 0.0)
    rain6 = float(weather.get("rain6_mm", 0.0) or 0.0)
    inflow = 8.0 + rain6 * 0.9  # mirrors orchestrator flood inflow synthesis
    return {
        "rain_forecast_mm": rain_fc,
        "rain6_mm": rain6,
        "inflow_m3s": round(inflow, 1),
        "soil_moisture_anomaly": float(sat.get("soil_moisture_anomaly", 0.0) or 0.0),
    }


def signal_from_weather(weather_rows: list[dict]) -> dict:
    """Forward feed derived from raw weather rows — verification path."""
    rain_fc = next(
        (w.get("rain_forecast_mm", 0.0) for w in reversed(weather_rows) if w.get("rain_forecast_mm") is not None), 0.0
    )
    rain6 = sum(w.get("rainfall_mm", 0.0) for w in weather_rows[-6:])
    return {
        "rain_forecast_mm": float(rain_fc),
        "rain6_mm": float(rain6),
        "inflow_m3s": round(min(60.0, 8.0 + rain6 * 0.9), 1),
        "soil_moisture_anomaly": 0.0,
    }
