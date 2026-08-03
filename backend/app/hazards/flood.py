"""Flood template — the calibrated Chennai monsoon hazard (default).

Formula weights and scale are the canonical flood model; moving them here
makes the engine hazard-parametric while keeping flood output identical.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _flood_probability(components: dict[str, float]) -> float:
    signal = (
        1.0 * components.get("rain_intensity", 0)
        + 0.8 * components.get("soil_moisture", 0)
        + 1.2 * components.get("headroom_deficit", 0)
        + 0.7 * components.get("drainage_stress", 0)
        + 0.3 * components.get("citizen_pressure", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=52.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    return {
        "rain_intensity": agg.get("weather", {}).get("rain_intensity", 0),
        "soil_moisture": agg.get("satellite", {}).get("soil_moisture_anomaly", 0),
        "headroom_deficit": agg.get("water", {}).get("headroom_deficit", 0),
        "drainage_stress": agg.get("water", {}).get("drainage_stress", 0),
        "citizen_pressure": agg.get("citizen_report", {}).get("citizen_pressure", 0),
        "aq_anomaly": agg.get("air_quality", {}).get("aq_anomaly", 0),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    return [
        {"rain_intensity": s["rainfall_mm"] * 1.0, "soil_moisture": 0.5, "headroom_deficit": 1.0,
         "drainage_stress": 0.8, "citizen_pressure": 0.2}
        for s in payload.get("weather_snapshots", [])[-48:]
    ]


def _flood_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    acc = sum(w["rainfall_mm"] for w in window[-6:])
    rain = min(12.0, acc / 16.0 * exposure)
    headroom = min(12.0, acc / 26.0 * exposure)
    stress = min(12.0, max(0.0, (acc / max(0.5, cap) - 8.0) / 3.0 * exposure))
    citizen = min(8.0, max(0.0, (stress - 9.0) * 0.8))
    return {
        "rain_intensity": round(rain, 3),
        "soil_moisture": round(soil, 3),
        "headroom_deficit": round(headroom, 3),
        "drainage_stress": round(stress, 3),
        "citizen_pressure": round(citizen, 3),
    }


def _flood_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "rain", "label": "Monsoon rainfall surge", "kind": "cause",
         "value": f"{components.get('rain_intensity', 0):.1f} mm/h", "confidence": 0.9},
        {"id": "soil", "label": "Pre-saturated soil", "kind": "cause",
         "value": f"anomaly {components.get('soil_moisture', 0):.2f}", "confidence": 0.8},
        {"id": "drainage", "label": "Stormwater network under load", "kind": "mechanism",
         "value": f"stress {components.get('drainage_stress', 0):.2f}", "confidence": 0.75},
        {"id": "headroom", "label": "Drainage headroom deficit", "kind": "mechanism",
         "value": f"{components.get('headroom_deficit', 0):.2f}/10", "confidence": 0.8},
        {"id": "reports", "label": "Verified waterlogging reports", "kind": "condition",
         "value": f"pressure {components.get('citizen_pressure', 0):.2f}", "confidence": 0.6},
        {"id": "risk", "label": f"Flood risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "rain", "target": "drainage", "label": "exceeds design capacity"},
        {"source": "soil", "target": "headroom", "label": "limits absorption"},
        {"source": "rain", "target": "headroom", "label": "raises water level"},
        {"source": "drainage", "target": "headroom", "label": "backlog reduces headroom"},
        {"source": "headroom", "target": "risk", "label": "approaches breach"},
        {"source": "reports", "target": "risk", "label": "ground truth confirms"},
    ]
    return {"nodes": nodes, "edges": edges}


def _flood_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_civic_1", "stakeholder": "civic", "priority": 1 if p > 0.55 else 2,
         "action": "Deploy pre-positioned pumps to lowest-lying wards and clear stormwater inlets.",
         "reasoning": "drainage stress is a top attribution feature; mechanical lift buys time.",
         "evidence_ids": []},
        {"id": "rec_responders_1", "stakeholder": "responders", "priority": 1 if sev >= 3 else 2,
         "action": "Stand by rescue teams near river-adjacent blocks; stage boats and generators.",
         "reasoning": "headroom deficit is approaching breach thresholds within the forecast horizon.",
         "evidence_ids": []},
        {"id": "rec_utilities_1", "stakeholder": "utilities", "priority": 2,
         "action": "Protect substations in flood-prone wards; prepare rolling load cuts.",
         "reasoning": "electrical infrastructure is vulnerable to water ingress.",
         "evidence_ids": []},
        {"id": "rec_public_1", "stakeholder": "public", "priority": 3,
         "action": "Avoid low-lying routes during peak hours; share verified waterlogging reports.",
         "reasoning": "ground reports improve nowcast precision for everyone.",
         "evidence_ids": []},
    ]


FLOOD = HazardSpec(
    id="flood",
    label="Flood",
    fusion=_fusion,
    history=_historical,
    formula=_flood_probability,
    features={
        "rain_intensity": "rain intensity",
        "soil_moisture": "soil moisture anomaly",
        "headroom_deficit": "drainage headroom deficit",
        "drainage_stress": "stormwater network stress",
        "citizen_pressure": "verified ground reports",
        "aq_anomaly": "air quality anomaly",
    },
    thresholds={"critical": 0.75, "high": 0.55, "moderate": 0.3},
    interventions=[
        {"id": "pump_preposition", "name": "Pump Preposition", "kind": "operational",
         "description": "Pre-position pumps at low-lying wards"},
        {"id": "reservoir_release", "name": "Reservoir Release", "kind": "operational",
         "description": "Coordinate reservoir release"},
        {"id": "drainage_clearing", "name": "Drainage Clearing", "kind": "engineering",
         "description": "Clear stormwater inlets"},
        {"id": "sandbagging", "name": "Sandbagging", "kind": "engineering",
         "description": "Sandbag river-adjacent blocks"},
        {"id": "evacuation_ready", "name": "Evacuation Ready", "kind": "policy",
         "description": "Stage shelters and routes"},
        {"id": "rainwater_harvesting", "name": "Rainwater Harvesting", "kind": "policy",
         "description": "Activate retention basins"},
    ],
    evidence=[
        EvidenceTemplate("imd-rain", "observation",
                         "6-hour rainfall accumulation entering design-threshold territory",
                         "rain_intensity", 3),
        EvidenceTemplate("gpm-nasa", "observation",
                         "satellite soil moisture anomaly exceeds 2σ seasonal baseline",
                         "soil_moisture", 3),
        EvidenceTemplate("cwprs-level", "observation",
                         "canal level within X% of drainage headroom limit",
                         "headroom_deficit", 2),
        EvidenceTemplate("civic-reports", "report",
                         "verified waterlogging reports from low-lying wards",
                         "citizen_pressure", 1),
        EvidenceTemplate("news-eom", "citation",
                         "official monsoon advisory active for the region",
                         None, 6),
    ],
    hourly=_flood_hourly,
    causal=_flood_causal,
    recommend=_flood_recommend,
    scale=52.0,
)