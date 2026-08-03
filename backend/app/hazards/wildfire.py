"""Wildfire template — fuel dryness, aridity, wind and thermal anomaly.

Second working hazard: proves the hazard-template seam. Features are derived
from the same canonical sensor tables (weather wind/humidity, satellite
dryness, citizen reports) so the demo theatre carries real provenance — every
component is still traceable to a tagged source.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _wildfire_probability(components: dict[str, float]) -> float:
    signal = (
        1.1 * components.get("fuel_dryness", 0)
        + 0.9 * components.get("aridity_index", 0)
        + 0.8 * components.get("wind_kick", 0)
        + 0.7 * components.get("thermal_anomaly", 0)
        + 0.3 * components.get("ignition_reports", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=46.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})

    soil = sat.get("soil_moisture_anomaly", 0)  # wetness anomaly — inverted for dryness
    swi = sat.get("surface_water_index", 0)
    wind = weather.get("wind_kmh", 0)
    humidity = weather.get("humidity", 60)
    rain6 = weather.get("rain6_mm", 0)

    return {
        "fuel_dryness": _clip(12.0 - soil * 2.2),
        "aridity_index": _clip(12.0 - rain6 / 6.0 - humidity / 25.0),
        "wind_kick": _clip(wind / 6.0),
        "thermal_anomaly": _clip(12.0 - swi * 3.0 + (12.0 - soil * 2.2) * 0.4),
        "ignition_reports": _clip(citizen.get("citizen_pressure", 0) * 2.0),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for s in payload.get("weather_snapshots", [])[-48:]:
        soil_proxy = max(0.0, 6.0 - s["rainfall_mm"] * 1.5)
        out.append({
            "fuel_dryness": _clip(12.0 - soil_proxy * 2.0),
            "aridity_index": _clip(12.0 - s["rainfall_mm"] * 2.0 - s.get("humidity", 60) / 25.0),
            "wind_kick": _clip(s.get("wind_kmh", 10) / 6.0),
            "thermal_anomaly": _clip(2.0 + s["rainfall_mm"] * 0.2),
            "ignition_reports": 0.2,
        })
    return out


def _wildfire_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    rain6 = sum(w["rainfall_mm"] for w in window[-6:])
    humidity = float(sum(w.get("humidity", 60) for w in window[-6:]) / max(1, len(window[-6:])))
    wind = float(max((w.get("wind_kmh", 0) for w in window[-6:]), default=0))
    return {
        "fuel_dryness": _clip(12.0 - soil * 2.2),
        "aridity_index": _clip(12.0 - rain6 / 6.0 - humidity / 25.0),
        "wind_kick": _clip(wind / 6.0),
        "thermal_anomaly": _clip(12.0 - soil * 2.2 - rain6 * 0.4),
        "ignition_reports": _clip((12.0 - humidity) * 0.2),
    }


def _wildfire_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "fuel", "label": "Vegetation fuel dryness", "kind": "cause",
         "value": f"{components.get('fuel_dryness', 0):.2f}/12", "confidence": 0.85},
        {"id": "aridity", "label": "Aridity index", "kind": "cause",
         "value": f"{components.get('aridity_index', 0):.2f}/12", "confidence": 0.8},
        {"id": "wind", "label": "Sustained wind gusts", "kind": "mechanism",
         "value": f"{components.get('wind_kick', 0) * 6:.0f} km/h", "confidence": 0.8},
        {"id": "thermal", "label": "Thermal anomaly (VIIRS)", "kind": "mechanism",
         "value": f"{components.get('thermal_anomaly', 0):.2f}/12", "confidence": 0.75},
        {"id": "ignition", "label": "Verified ignition reports", "kind": "condition",
         "value": f"{components.get('ignition_reports', 0) / 2:.1f} sightings", "confidence": 0.6},
        {"id": "risk", "label": f"Wildfire risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "aridity", "target": "fuel", "label": "dries fuels below moisture floor"},
        {"source": "wind", "target": "risk", "label": "accelerates spread"},
        {"source": "fuel", "target": "thermal", "label": "sustains heat signature"},
        {"source": "thermal", "target": "ignition", "label": "smoke/ignition confirmed"},
        {"source": "ignition", "target": "risk", "label": "active start"},
        {"source": "wind", "target": "risk", "label": "drives flank alignment"},
    ]
    return {"nodes": nodes, "edges": edges}


def _wildfire_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_fire_1", "stakeholder": "responders", "priority": 1 if p > 0.6 else 2,
         "action": "Hold containment lines on the windward flank; task air tankers to first ignition.",
         "reasoning": "wind kick is a top spread driver; aviation buys containment time.",
         "evidence_ids": []},
        {"id": "rec_wui_1", "stakeholder": "civic", "priority": 1 if sev >= 3 else 2,
         "action": "Open evacuation corridors in wildland-urban interface blocks before wind shift.",
         "reasoning": "interface blocks are the highest life-exposure zones under red-flag conditions.",
         "evidence_ids": []},
        {"id": "rec_utility_1", "stakeholder": "utilities", "priority": 2,
         "action": "De-energize feeders along ridgelines; dispatch line crews to downed conductors.",
         "reasoning": "ignition sources cluster around distribution infrastructure in high wind.",
         "evidence_ids": []},
        {"id": "rec_public_1", "stakeholder": "public", "priority": 3,
         "action": "Report smoke and heat signatures immediately; keep fire-escape lanes clear.",
         "reasoning": "early ground truth sharpens thermal anomaly verification.",
         "evidence_ids": []},
    ]


WILDFIRE = HazardSpec(
    id="wildfire",
    label="Wildfire",
    fusion=_fusion,
    history=_historical,
    formula=_wildfire_probability,
    features={
        "fuel_dryness": "vegetation fuel dryness",
        "aridity_index": "aridity index",
        "wind_kick": "sustained wind gusts",
        "thermal_anomaly": "thermal anomaly (VIIRS)",
        "ignition_reports": "verified ignition reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {"id": "containment_lines", "name": "Containment Lines", "kind": "engineering",
         "description": "Cut fire breaks on the windward flank"},
        {"id": "air_tankers_standby", "name": "Air Tankers Standby", "kind": "operational",
         "description": "Stage water/retardant drops for first-response ignition"},
        {"id": "fuel_break_clearing", "name": "Fuel Break Clearing", "kind": "engineering",
         "description": "Clear dead vegetation along ridge roads"},
        {"id": "evacuation_corridors", "name": "Evacuation Corridors", "kind": "policy",
         "description": "Open and sign evacuation corridors ahead of wind shift"},
        {"id": "water_tenders", "name": "Water Tenders", "kind": "operational",
         "description": "Pre-position tenders at wildland-urban interface blocks"},
    ],
    evidence=[
        EvidenceTemplate("noaa-firewx", "observation",
                         "fuel moisture content below the seasonal floor",
                         "fuel_dryness", 3),
        EvidenceTemplate("viiirs-thermal", "observation",
                         "VIIRS thermal anomaly clusters detected on adjacent ridgelines",
                         "thermal_anomaly", 2),
        EvidenceTemplate("noaa-firewx", "observation",
                         "sustained wind gusts above red-flag threshold",
                         "wind_kick", 2),
        EvidenceTemplate("civic-reports", "report",
                         "verified smoke/ignition sightings from populated foothills",
                         "ignition_reports", 1),
        EvidenceTemplate("news-eom", "citation",
                         "red-flag warning active for the county",
                         None, 6),
    ],
    hourly=_wildfire_hourly,
    causal=_wildfire_causal,
    recommend=_wildfire_recommend,
    scale=46.0,
)