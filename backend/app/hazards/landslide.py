"""Landslide template — rainfall-triggered slope failure.

Classic threshold model: a rain burst on already-saturated soil above a fragile
slope. Uses canonical telemetry only (rain, soil moisture, exposure/elevation,
citizen reports) — the same physics that drives flood, applied to slope
mobilization. Slope fragility is encoded through exposure (steep terrain zones
carry high exposure in the seed pack).
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _ls_probability(components: dict[str, float]) -> float:
    signal = (
        1.0 * components.get("slope_saturation", 0)
        + 1.0 * components.get("rain_trigger", 0)
        + 0.9 * components.get("terrain_fragility", 0)
        + 0.5 * components.get("slippage_report", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=48.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})
    exposure = payload.get("exposure", 1.0)

    soil = sat.get("soil_moisture_anomaly", 0)
    rain6 = weather.get("rain6_mm", 0)
    intensity = weather.get("rain_intensity", 0)
    return {
        "slope_saturation": _clip(soil * 1.6 + rain6 / 7.0),
        "rain_trigger": _clip(intensity * 1.5 + rain6 / 9.0),
        "terrain_fragility": _clip(exposure * 3.0),
        "slippage_report": _clip(citizen.get("citizen_pressure", 0) * 2.2),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for s in payload.get("weather_snapshots", [])[-48:]:
        rain = s["rainfall_mm"]
        out.append(
            {
                "slope_saturation": _clip(6.0 + rain * 0.5),
                "rain_trigger": _clip(3.0 + rain * 0.6),
                "terrain_fragility": 3.5,
                "slippage_report": 0.3,
            }
        )
    return out


def _ls_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    rain6 = sum(w["rainfall_mm"] for w in window[-6:])
    return {
        "slope_saturation": _clip(soil * 1.6 + rain6 / 7.0),
        "rain_trigger": _clip(rain6 / 4.5),
        "terrain_fragility": _clip(exposure * 3.0),
        "slippage_report": _clip(rain6 * 0.4),
    }


def _ls_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {
            "id": "sat",
            "label": "Slope saturation",
            "kind": "cause",
            "value": f"{components.get('slope_saturation', 0):.2f}/12",
            "confidence": 0.85,
        },
        {
            "id": "rain",
            "label": "Rain burst trigger",
            "kind": "cause",
            "value": f"{components.get('rain_trigger', 0):.2f}/12",
            "confidence": 0.85,
        },
        {
            "id": "terrain",
            "label": "Terrain fragility",
            "kind": "condition",
            "value": f"{components.get('terrain_fragility', 0):.2f}/12",
            "confidence": 0.75,
        },
        {
            "id": "slip",
            "label": "Slippage reports",
            "kind": "condition",
            "value": f"{components.get('slippage_report', 0):.1f} reports",
            "confidence": 0.6,
        },
        {
            "id": "risk",
            "label": f"Landslide risk ({pred.get('risk_probability', 0):.0%})",
            "kind": "risk",
            "value": f"severity {pred.get('severity', 0):.1f}/5",
            "confidence": pred.get("confidence", 0.5),
        },
    ]
    edges = [
        {"source": "sat", "target": "risk", "label": "pore pressure exceeds friction"},
        {"source": "rain", "target": "sat", "label": "burst adds load on wet slope"},
        {"source": "terrain", "target": "risk", "label": "steep/fragile geometry mobilizes"},
        {"source": "slip", "target": "rain", "label": "surface movement confirms trigger"},
        {"source": "slip", "target": "risk", "label": "early movement precedes runout"},
    ]
    return {"nodes": nodes, "edges": edges}


def _ls_recommend(p: float, sev: float) -> list:
    return [
        {
            "id": "rec_ls_1",
            "stakeholder": "responders",
            "priority": 1 if p > 0.6 else 2,
            "action": "Close hillside corridor segments under active saturation.",
            "reasoning": "runout corridors are the highest life-exposure reach.",
            "evidence_ids": [],
        },
        {
            "id": "rec_ls_2",
            "stakeholder": "civic",
            "priority": 1 if sev >= 3 else 2,
            "action": "Relocate settlements at the base of monitored slopes.",
            "reasoning": "mobilization follows saturation within the burst window.",
            "evidence_ids": [],
        },
        {
            "id": "rec_ls_3",
            "stakeholder": "utilities",
            "priority": 2,
            "action": "Protect culverts and drainage cuts from debris blockage.",
            "reasoning": "blocked drainage turns a slope event into a debris flow.",
            "evidence_ids": [],
        },
        {
            "id": "rec_ls_4",
            "stakeholder": "public",
            "priority": 3,
            "action": "Report cracks, tilting poles and new springs immediately.",
            "reasoning": "pre-mobilization indicators precede runout by hours.",
            "evidence_ids": [],
        },
    ]


LANDSLIDE = HazardSpec(
    id="landslide",
    label="Landslide",
    fusion=_fusion,
    history=_historical,
    formula=_ls_probability,
    features={
        "slope_saturation": "slope saturation",
        "rain_trigger": "rain burst trigger",
        "terrain_fragility": "terrain fragility",
        "slippage_report": "slippage reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {
            "id": "corridor_closure",
            "name": "Hillside Corridor Closure",
            "kind": "policy",
            "description": "Close runout corridors during active saturation",
        },
        {
            "id": "slope_relocation",
            "name": "Slope-Base Relocation",
            "kind": "policy",
            "description": "Relocate settlements at monitored slope bases",
        },
        {
            "id": "debris_drain_clearing",
            "name": "Debris Drain Clearing",
            "kind": "engineering",
            "description": "Protect culverts and cuts from debris blockage",
        },
        {
            "id": "slope_anchoring",
            "name": "Slope Anchoring",
            "kind": "engineering",
            "description": "Install anchors and drainage on critical faces",
        },
        {
            "id": "monitoring_teams",
            "name": "Slope Monitoring",
            "kind": "operational",
            "description": "Crack-meter and gauge watch on active faces",
        },
    ],
    evidence=[
        EvidenceTemplate(
            "imd-rain", "observation", "rain burst above the slope-failure intensity threshold", "rain_trigger", 2
        ),
        EvidenceTemplate(
            "gpm-nasa", "observation", "soil saturation above the mobilization floor", "slope_saturation", 2
        ),
        EvidenceTemplate("civic-reports", "report", "reported cracks, tilting poles and springs", "slippage_report", 1),
        EvidenceTemplate("news-eom", "citation", "landslide watch active for the hill district", None, 6),
    ],
    hourly=_ls_hourly,
    causal=_ls_causal,
    recommend=_ls_recommend,
    scale=48.0,
)
