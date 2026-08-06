"""Heatwave template — heat-dome / wet-bulb stress model.

Heat hazard is driven by temperature-load proxies we can honestly derive from
the canonical tables: low humidity (dry air heats faster), rain deficit
(dry ground absorbs heat), wind stagnation (no mixing), and heat-illness
reports as ground truth. A wet-bulb-style coupling is approximated by humidity
terms — the honest label is "thermal stress", not a thermometer reading.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _hw_probability(components: dict[str, float]) -> float:
    signal = (
        1.0 * components.get("thermal_excess", 0)
        + 1.0 * components.get("dry_bulb_load", 0)
        + 0.8 * components.get("stagnation", 0)
        + 0.6 * components.get("heat_illness", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=46.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    citizen = agg.get("citizen_report", {})
    sat = agg.get("satellite", {})

    humidity = weather.get("humidity", 60)
    rain6 = weather.get("rain6_mm", 0)
    wind = weather.get("wind_kmh", 12)
    soil = sat.get("soil_moisture_anomaly", 0)
    return {
        "thermal_excess": _clip(12.0 - humidity / 6.0 - rain6 / 4.0),
        "dry_bulb_load": _clip(12.0 - soil * 1.5 - rain6 / 3.0),
        "stagnation": _clip(12.0 - wind / 3.0),
        "heat_illness": _clip(citizen.get("citizen_pressure", 0) * 2.8),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for s in payload.get("weather_snapshots", [])[-48:]:
        rain = s["rainfall_mm"]
        hum = s.get("humidity", 60)
        out.append(
            {
                "thermal_excess": _clip(12.0 - hum / 6.0 - rain * 0.5),
                "dry_bulb_load": _clip(9.0 - rain * 1.2),
                "stagnation": _clip(8.0 - s.get("wind_kmh", 12) / 4.0),
                "heat_illness": 0.4,
            }
        )
    return out


def _hw_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    humidity = float(sum(w.get("humidity", 60) for w in window[-6:]) / max(1, len(window[-6:])))
    rain6 = sum(w["rainfall_mm"] for w in window[-6:])
    wind = float(max((w.get("wind_kmh", 0) for w in window[-6:]), default=12))
    return {
        "thermal_excess": _clip(12.0 - humidity / 6.0 - rain6 / 4.0),
        "dry_bulb_load": _clip(12.0 - soil * 1.5 - rain6 / 3.0),
        "stagnation": _clip(12.0 - wind / 3.0),
        "heat_illness": _clip((12.0 - humidity) * 0.4),
    }


def _hw_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {
            "id": "thermal",
            "label": "Thermal excess",
            "kind": "cause",
            "value": f"{components.get('thermal_excess', 0):.2f}/12",
            "confidence": 0.85,
        },
        {
            "id": "bulb",
            "label": "Dry-bulb load",
            "kind": "mechanism",
            "value": f"{components.get('dry_bulb_load', 0):.2f}/12",
            "confidence": 0.8,
        },
        {
            "id": "stag",
            "label": "Wind stagnation",
            "kind": "mechanism",
            "value": f"{components.get('stagnation', 0):.2f}/12",
            "confidence": 0.75,
        },
        {
            "id": "illness",
            "label": "Heat-illness reports",
            "kind": "condition",
            "value": f"{components.get('heat_illness', 0):.1f} reports",
            "confidence": 0.6,
        },
        {
            "id": "risk",
            "label": f"Heatwave risk ({pred.get('risk_probability', 0):.0%})",
            "kind": "risk",
            "value": f"severity {pred.get('severity', 0):.1f}/5",
            "confidence": pred.get("confidence", 0.5),
        },
    ]
    edges = [
        {"source": "thermal", "target": "risk", "label": "heat load exceeds comfort floor"},
        {"source": "bulb", "target": "risk", "label": "dry ground amplifies daytime peak"},
        {"source": "stag", "target": "thermal", "label": "no mixing holds the heat dome"},
        {"source": "illness", "target": "risk", "label": "health system pressure"},
        {"source": "stag", "target": "illness", "label": "night floor stays high"},
    ]
    return {"nodes": nodes, "edges": edges}


def _hw_recommend(p: float, sev: float) -> list:
    return [
        {
            "id": "rec_hw_1",
            "stakeholder": "responders",
            "priority": 1 if p > 0.6 else 2,
            "action": "Open cooling centres in the stagnation envelope and staff them for night hours.",
            "reasoning": "night-floor heat is where mortality concentrates.",
            "evidence_ids": [],
        },
        {
            "id": "rec_hw_2",
            "stakeholder": "civic",
            "priority": 1 if sev >= 3 else 2,
            "action": "Reschedule outdoor labour windows to pre-dawn; suspend midday events.",
            "reasoning": "occupational exposure drives the illness curve.",
            "evidence_ids": [],
        },
        {
            "id": "rec_hw_3",
            "stakeholder": "utilities",
            "priority": 2,
            "action": "Protect grid capacity for the cooling-load peak; prep rolling-load protocol.",
            "reasoning": "cooling demand spikes exactly when the grid is weakest.",
            "evidence_ids": [],
        },
        {
            "id": "rec_hw_4",
            "stakeholder": "public",
            "priority": 3,
            "action": "Report heat illness and power outages in the hot corridor.",
            "reasoning": "ground truth maps the exposure envelope faster than forecast.",
            "evidence_ids": [],
        },
    ]


HEATWAVE = HazardSpec(
    id="heatwave",
    label="Heatwave",
    fusion=_fusion,
    history=_historical,
    formula=_hw_probability,
    features={
        "thermal_excess": "thermal excess",
        "dry_bulb_load": "dry-bulb load",
        "stagnation": "wind stagnation",
        "heat_illness": "heat-illness reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {
            "id": "cooling_centres",
            "name": "Cooling Centres",
            "kind": "operational",
            "description": "Open and staff cooling centres for night hours",
        },
        {
            "id": "labour_rescheduling",
            "name": "Labour Rescheduling",
            "kind": "policy",
            "description": "Pre-dawn outdoor work windows; suspend midday events",
        },
        {
            "id": "grid_cooling_protection",
            "name": "Grid Cooling Protection",
            "kind": "engineering",
            "description": "Protect capacity for the cooling-load peak",
        },
        {
            "id": "water_stations",
            "name": "Water Stations",
            "kind": "operational",
            "description": "Street water and shade stations in the hot corridor",
        },
        {
            "id": "school_heat_protocol",
            "name": "School Heat Protocol",
            "kind": "policy",
            "description": "Half-day or closure protocol during heat-dome peaks",
        },
    ],
    evidence=[
        EvidenceTemplate(
            "noaa-firewx",
            "observation",
            "humidity and rain deficit consistent with heat-dome load",
            "thermal_excess",
            3,
        ),
        EvidenceTemplate(
            "gpm-nasa", "observation", "dry ground with no recharge ahead of the hot spell", "dry_bulb_load", 3
        ),
        EvidenceTemplate("civic-reports", "report", "reported heat illness and power outages", "heat_illness", 2),
        EvidenceTemplate("news-eom", "citation", "heat advisory active for the region", None, 6),
    ],
    hourly=_hw_hourly,
    causal=_hw_causal,
    recommend=_hw_recommend,
    scale=46.0,
)
