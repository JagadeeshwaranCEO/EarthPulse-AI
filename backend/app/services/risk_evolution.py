"""Risk Evolution — per-hour replayed trajectory for a location.

Recomputes the pipeline's feature math (WeatherAgent accumulation, WaterAgent
headroom/stress, satellite soil moisture, citizen pressure) for *every simulated
hour* of the seed window, then squashes through the canonical
probability_from_components. Produces an honest hour-by-hour risk curve that is
exactly consistent with the live dashboard value at the current clock hour.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.models import Location, SatelliteFrame, WeatherSnapshot
from app.services.ticker import current_hour


def _satellite_soil(frames: list[dict], hour: int) -> float:
    """Soil moisture anomaly at a simulated hour (satellite frames every 2h).

    At clock hour H the pipeline consumes frames[0..H//2), so the latest usable
    frame covers ~H-1. Beyond the stored window we decay the last frame (matches
    orchestrator extrapolation).
    """
    if not frames:
        return 0.0
    idx = (max(1, int(hour)) - 1) // 2
    if idx < len(frames):
        return min(12.0, float(frames[idx]["soil_moisture_anomaly"]))
    last = frames[-1]["soil_moisture_anomaly"]
    over = idx - len(frames) + 1
    return min(12.0, max(0.0, last * (0.94**over)))


def _window(weather: list[dict], hour: float) -> list[dict]:
    """Weather window at a simulated hour — matches orchestrator consumption."""
    h = int(hour)
    n = min(72, max(1, h))
    window = weather[max(0, n - 6) : n]
    if h > 72 and weather:
        last = weather[-1]
        for k in range(1, min(h - 72, 8) + 1):
            window.append({**last, "rainfall_mm": last["rainfall_mm"] * (0.86**k), "wind_kmh": last.get("wind_kmh", 0)})
    return window


def hour_components(
    hazard_id: str, weather: list[dict], sat: list[dict], hour: float, exposure: float, cap_mmh: float
) -> dict[str, float]:
    """Hazard-templated components at a simulated hour."""
    from app.hazards.registry import get_hazard

    hazard = get_hazard(hazard_id)
    soil = _satellite_soil(sat, hour)
    if hazard.hourly:
        return hazard.hourly(_window(weather, hour), soil, exposure, cap_mmh)
    return hazard.fusion({})


def _level(p: float) -> str:
    return "critical" if p >= 0.75 else "high" if p >= 0.55 else "moderate" if p >= 0.3 else "low"


def evolution(db, location: Location, lookback_h: int = 48, horizon_h: int = 24) -> dict:
    """Hourly risk curve from (current − lookback) → (current + horizon)."""
    from app.hazards.registry import get_hazard

    hazard = get_hazard(location.hazard_type)
    hour = current_hour()
    exposure = (location.attributes or {}).get("exposure", 1.0)
    cap = location.drainage_capacity_mmh

    weather = [
        {"rainfall_mm": w.rainfall_mm, "humidity": w.humidity, "wind_kmh": w.wind_kmh}
        for w in (
            db.query(WeatherSnapshot).filter_by(location_id=location.id).order_by(WeatherSnapshot.captured_at).all()
        )
    ]
    sat = [
        {"soil_moisture_anomaly": f.soil_moisture_anomaly}
        for f in (
            db.query(SatelliteFrame).filter_by(location_id=location.id).order_by(SatelliteFrame.captured_at).all()
        )
    ]

    start = max(0, int(hour) - lookback_h)
    points = []
    for h in range(start, int(hour) + horizon_h + 1):
        comps = hour_components(hazard.id, weather, sat, h, exposure, cap)
        p = hazard.probability(comps)
        points.append(
            {
                "hour": h,
                "simulated_at": datetime.now(timezone.utc),
                "risk_probability": round(p, 3),
                "level": hazard.level(p),
                "components": comps,
                "is_now": h == int(hour),
            }
        )

    probs = [pt["risk_probability"] for pt in points]
    peak_idx = probs.index(max(probs))
    now_idx = points.index(next(pt for pt in points if pt["is_now"]))
    delta_24h = round(probs[min(now_idx + 24, len(probs) - 1)] - probs[now_idx], 3) if now_idx < len(probs) - 1 else 0.0
    return {
        "location_id": location.id,
        "now_hour": int(hour),
        "points": points,
        "peak_probability": round(probs[peak_idx], 3),
        "peak_at_hour": points[peak_idx]["hour"],
        "now_probability": round(probs[now_idx], 3),
        "delta_24h": delta_24h,
        "generated_at": datetime.now(timezone.utc),
    }
