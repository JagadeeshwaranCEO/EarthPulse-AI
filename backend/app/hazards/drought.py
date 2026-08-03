"""Drought template — slow-onset moisture deficit.

Drought is the slow hazard: precipitation deficit, soil desiccation and heat
stress compound over weeks. Components invert the canonical wetness signals
(rain, soil moisture, humidity) so the same tables drive it; water-scarcity
reports anchor ground truth. The hourly curve uses the same formula, so the
evolution engine naturally shows the slow creep.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _dr_probability(components: dict[str, float]) -> float:
    signal = (
        1.1 * components.get("precipitation_deficit", 0)
        + 1.0 * components.get("soil_desiccation", 0)
        + 0.7 * components.get("heat_stress", 0)
        + 0.5 * components.get("water_scarcity", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=46.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})

    rain6 = weather.get("rain6_mm", 0)
    humidity = weather.get("humidity", 60)
    soil = sat.get("soil_moisture_anomaly", 0)
    return {
        "precipitation_deficit": _clip(12.0 - rain6 / 2.0),
        "soil_desiccation": _clip(12.0 - soil * 1.8),
        "heat_stress": _clip(12.0 - humidity / 8.0),
        "water_scarcity": _clip(citizen.get("citizen_pressure", 0) * 3.0),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for s in payload.get("weather_snapshots", [])[-48:]:
        rain = s["rainfall_mm"]
        out.append({
            "precipitation_deficit": _clip(12.0 - rain * 2.0),
            "soil_desiccation": _clip(10.0 - rain * 1.5),
            "heat_stress": _clip(6.0 - rain * 0.5),
            "water_scarcity": 0.4,
        })
    return out


def _dr_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    rain6 = sum(w["rainfall_mm"] for w in window[-6:])
    humidity = float(sum(w.get("humidity", 60) for w in window[-6:]) / max(1, len(window[-6:])))
    return {
        "precipitation_deficit": _clip(12.0 - rain6 / 2.0),
        "soil_desiccation": _clip(12.0 - soil * 1.8),
        "heat_stress": _clip(12.0 - humidity / 8.0),
        "water_scarcity": _clip(rain6 * -0.4 + 6.0),
    }


def _dr_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "precip", "label": "Precipitation deficit", "kind": "cause",
         "value": f"{components.get('precipitation_deficit', 0):.2f}/12", "confidence": 0.9},
        {"id": "soil", "label": "Soil desiccation", "kind": "mechanism",
         "value": f"{components.get('soil_desiccation', 0):.2f}/12", "confidence": 0.85},
        {"id": "heat", "label": "Heat stress", "kind": "mechanism",
         "value": f"{components.get('heat_stress', 0):.2f}/12", "confidence": 0.8},
        {"id": "scarcity", "label": "Water scarcity reports", "kind": "condition",
         "value": f"{components.get('water_scarcity', 0):.1f} reports", "confidence": 0.6},
        {"id": "risk", "label": f"Drought risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "precip", "target": "soil", "label": "no recharge → desiccation"},
        {"source": "heat", "target": "soil", "label": "evaporative demand drains moisture"},
        {"source": "soil", "target": "risk", "label": "agro-hydrological stress"},
        {"source": "scarcity", "target": "risk", "label": "domestic supply strain"},
        {"source": "heat", "target": "scarcity", "label": "demand spikes with heat"},
    ]
    return {"nodes": nodes, "edges": edges}


def _dr_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_dr_1", "stakeholder": "responders", "priority": 1 if p > 0.6 else 2,
         "action": "Activate water-tanker corridors for the scarcity-report clusters.",
         "reasoning": "scarcity reports lead supply failure by days.",
         "evidence_ids": []},
        {"id": "rec_dr_2", "stakeholder": "civic", "priority": 1 if sev >= 3 else 2,
         "action": "Issue volumetric rationing ahead of reservoir trigger lines.",
         "reasoning": "rationing before collapse preserves essential uses.",
         "evidence_ids": []},
        {"id": "rec_dr_3", "stakeholder": "utilities", "priority": 2,
         "action": "Protect groundwater borefields and repair losses in the distribution net.",
         "reasoning": "network loss is the cheapest recoverable deficit.",
         "evidence_ids": []},
        {"id": "rec_dr_4", "stakeholder": "public", "priority": 3,
         "action": "Report dry taps and failing borewells through the civic channel.",
         "reasoning": "ground truth maps the scarcity envelope faster than gauges.",
         "evidence_ids": []},
    ]


DROUGHT = HazardSpec(
    id="drought",
    label="Drought",
    fusion=_fusion,
    history=_historical,
    formula=_dr_probability,
    features={
        "precipitation_deficit": "precipitation deficit",
        "soil_desiccation": "soil desiccation",
        "heat_stress": "heat stress",
        "water_scarcity": "water scarcity reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {"id": "tanker_corridors", "name": "Water Tanker Corridors", "kind": "operational",
         "description": "Tanker supply for scarcity-report clusters"},
        {"id": "volumetric_rationing", "name": "Volumetric Rationing", "kind": "policy",
         "description": "Rationing ahead of reservoir trigger lines"},
        {"id": "borefield_protection", "name": "Borefield Protection", "kind": "engineering",
         "description": "Protect groundwater sources and repair network loss"},
        {"id": "crop_switching", "name": "Crop Switching", "kind": "policy",
         "description": "Drought-resilient crop substitution advisory"},
        {"id": "reservoir_release_plan", "name": "Reservoir Release Plan", "kind": "operational",
         "description": "Trigger-line release plan for essential use"},
    ],
    evidence=[
        EvidenceTemplate("imd-rain", "observation",
                         "precipitation below the deficit threshold over the window",
                         "precipitation_deficit", 4),
        EvidenceTemplate("gpm-nasa", "observation",
                         "soil moisture anomaly in persistent deficit",
                         "soil_desiccation", 4),
        EvidenceTemplate("civic-reports", "report",
                         "reported dry taps and failing borewells",
                         "water_scarcity", 2),
        EvidenceTemplate("news-eom", "citation",
                         "drought advisory active for the district",
                         None, 8),
    ],
    hourly=_dr_hourly,
    causal=_dr_causal,
    recommend=_dr_recommend,
    scale=46.0,
)
