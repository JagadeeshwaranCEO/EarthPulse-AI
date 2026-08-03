"""Planet Pulse Score — unified 0..1000 regional stability metric.

Score = 1000 − Σ(penalty_i). Penalties derive from fused risk components, anomaly
scores, and active alerts. Bands: stable (≥750), watchful (550–749), stressed
(300–549), critical (<300). Every point of the score is attributable to a factor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PulseResult:
    score: float
    factors: dict[str, float]
    band: str


_PENALTY_CAP = {"flood": 600, "wildfire": 400, "dumping": 150}


def _band(score: float) -> str:
    if score >= 750:
        return "stable"
    if score >= 550:
        return "watchful"
    if score >= 300:
        return "stressed"
    return "critical"


def compute_pulse(
    components: dict[str, float],
    anomaly_score: float,
    active_alerts: int,
    event_type: str = "flood",
) -> PulseResult:
    penalties: dict[str, float] = {}

    p_rain = min(1.0, components.get("rain_intensity", 0) / 12.0)
    p_soil = min(1.0, components.get("soil_moisture", 0) / 10.0)
    p_head = min(1.0, components.get("headroom_deficit", 0) / 10.0)
    p_drain = min(1.0, components.get("drainage_stress", 0) / 10.0)
    p_cit = min(1.0, components.get("citizen_pressure", 0) / 8.0)

    cap = _PENALTY_CAP.get(event_type, 300)
    hazard = cap * (0.45 * p_rain + 0.25 * p_soil + 0.30 * p_head)
    penalties["hazard"] = round(hazard, 1)
    penalties["drainage_load"] = round(cap * 0.15 * p_drain, 1)
    penalties["anomaly"] = round(120 * anomaly_score, 1)
    penalties["community_signals"] = round(80 * p_cit, 1)
    penalties["active_alerts"] = round(min(150, 50 * active_alerts), 1)

    score = float(max(0.0, 1000.0 - sum(penalties.values())))
    return PulseResult(score=round(score, 1), factors=penalties, band=_band(score))
