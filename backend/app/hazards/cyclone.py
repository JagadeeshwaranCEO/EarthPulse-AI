"""Cyclone template — Bay of Bengal / Arabian Sea tropical cyclone.

Third working hazard: an India-critical coastal theatre. Components come from the
same canonical sensor tables (weather wind/rain, satellite surface moisture,
citizen reports) so the demo theatre carries real provenance — every component
traces to a tagged source. Wind field is the dominant driver; storm-surge
coupling and rain burst feed flood cascades downstream.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _cyclone_probability(components: dict[str, float]) -> float:
    signal = (
        1.2 * components.get("storm_wind", 0)
        + 1.1 * components.get("surge_coupling", 0)
        + 0.9 * components.get("rain_burst", 0)
        + 0.6 * components.get("track_pressure", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=48.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    weather = agg.get("weather", {})
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})

    wind = weather.get("wind_kmh", 0)
    humidity = weather.get("humidity", 60)
    rain6 = weather.get("rain6_mm", 0)
    swi = sat.get("surface_water_index", 0)

    return {
        "storm_wind": _clip(wind / 5.5),
        "surge_coupling": _clip(swi * 4.0 + wind / 16.0),
        "rain_burst": _clip(rain6 / 8.0 + humidity / 30.0),
        "track_pressure": _clip(12.0 - swi * 3.0 + citizen.get("citizen_pressure", 0)),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for s in payload.get("weather_snapshots", [])[-48:]:
        wind = s.get("wind_kmh", 12)
        out.append({
            "storm_wind": _clip(wind / 5.5),
            "surge_coupling": _clip(s["rainfall_mm"] * 0.6 + wind / 16.0),
            "rain_burst": _clip(s["rainfall_mm"] / 3.0),
            "track_pressure": _clip(2.0 + s["rainfall_mm"] * 0.3),
        })
    return out


def _cyclone_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    wind = float(max((w.get("wind_kmh", 0) for w in window[-6:]), default=0))
    rain6 = sum(w["rainfall_mm"] for w in window[-6:])
    humidity = float(sum(w.get("humidity", 60) for w in window[-6:]) / max(1, len(window[-6:])))
    swi = max(0.0, soil / 12.0)
    return {
        "storm_wind": _clip(wind / 5.5),
        "surge_coupling": _clip(swi * 4.0 + wind / 16.0),
        "rain_burst": _clip(rain6 / 8.0 + humidity / 30.0),
        "track_pressure": _clip(12.0 - soil / 2.0),
    }


def _cyclone_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "wind", "label": "Cyclone wind field", "kind": "cause",
         "value": f"{components.get('storm_wind', 0) * 5.5:.0f} km/h", "confidence": 0.85},
        {"id": "surge", "label": "Storm surge coupling", "kind": "mechanism",
         "value": f"{components.get('surge_coupling', 0):.2f}/12", "confidence": 0.8},
        {"id": "rain", "label": "Rain burst band", "kind": "cause",
         "value": f"{components.get('rain_burst', 0):.2f}/12", "confidence": 0.78},
        {"id": "track", "label": "Track/pressure gradient", "kind": "condition",
         "value": f"{components.get('track_pressure', 0):.2f}/12", "confidence": 0.7},
        {"id": "risk", "label": f"Cyclone risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "wind", "target": "surge", "label": "pushes surge onshore"},
        {"source": "surge", "target": "risk", "label": "coastal inundation"},
        {"source": "rain", "target": "risk", "label": "inland flooding"},
        {"source": "track", "target": "risk", "label": "sharpens landfall timing"},
        {"source": "wind", "target": "rain", "label": "spiral band convergence"},
    ]
    return {"nodes": nodes, "edges": edges}


def _cyclone_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_cyc_1", "stakeholder": "responders", "priority": 1 if p > 0.6 else 2,
         "action": "Pre-position boats and rescue teams along the predicted surge reach before landfall.",
         "reasoning": "surge windows are compressed; pre-deployment beats post-landfall insertion.",
         "evidence_ids": []},
        {"id": "rec_cyc_2", "stakeholder": "civic", "priority": 1 if sev >= 3 else 2,
         "action": "Order phased coastal evacuation and open cyclone shelters beyond the surge line.",
         "reasoning": "coastal blocks are the highest life-exposure reach under wind-plus-surge.",
         "evidence_ids": []},
        {"id": "rec_cyc_3", "stakeholder": "utilities", "priority": 2,
         "action": "Pre-stage grid shutoff and harden transmission along the landfall arc.",
         "reasoning": "downed conductors follow the wind field hours ahead of the eyewall.",
         "evidence_ids": []},
        {"id": "rec_cyc_4", "stakeholder": "public", "priority": 3,
         "action": "Broadcast landfall-time and survival-kit guidance; hold harbour/port clearances.",
         "reasoning": "timing beats totals — a compressed surge window dominates the response clock.",
         "evidence_ids": []},
    ]


CYCLONE = HazardSpec(
    id="cyclone",
    label="Cyclone",
    fusion=_fusion,
    history=_historical,
    formula=_cyclone_probability,
    features={
        "storm_wind": "cyclone wind field",
        "surge_coupling": "storm surge coupling",
        "rain_burst": "rain burst band",
        "track_pressure": "track / pressure gradient",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {"id": "coastal_evacuation", "name": "Coastal Evacuation", "kind": "policy",
         "description": "Ordered evacuation of surge-range coastal blocks"},
        {"id": "cyclone_shelters", "name": "Cyclone Shelters", "kind": "engineering",
         "description": "Open and stock cyclone shelters beyond the surge line"},
        {"id": "boat_preposition", "name": "Boat Pre-positioning", "kind": "operational",
         "description": "Pre-stage rescue boats behind the tidal surge corridor"},
        {"id": "grid_hardening", "name": "Grid Hardening", "kind": "engineering",
         "description": "Shut down / harden distribution along the wind arc"},
        {"id": "port_closure", "name": "Port Closure", "kind": "policy",
         "description": "Hold harbour clearances and close fishing fleets to sea"},
    ],
    evidence=[
        EvidenceTemplate("imd-cyclone", "forecast",
                         "IMD cyclone track cone places the theatre in the danger swath",
                         "track_pressure", 3),
        EvidenceTemplate("noaa-firewx", "observation",
                         "sustained wind field above cyclone threshold",
                         "storm_wind", 2),
        EvidenceTemplate("gpm-nasa", "observation",
                         "surface moisture amplification ahead of the surge",
                         "surge_coupling", 2),
        EvidenceTemplate("civic-reports", "report",
                         "reported sea-state rise and standing water along coastal wards",
                         "surge_coupling", 1),
        EvidenceTemplate("news-eom", "citation",
                         "storm surge warning active for the coastal district",
                         None, 6),
    ],
    hourly=_cyclone_hourly,
    causal=_cyclone_causal,
    recommend=_cyclone_recommend,
    scale=48.0,
)