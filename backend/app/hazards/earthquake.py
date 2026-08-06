"""Earthquake template — seismic early-warning / aftershock-risk model.

Honest framing: deterministic earthquake *prediction* is not defensible science.
This spec models what IS defensible — a seismic episode monitor: ground-motion
telemetry (accel), accumulated energy release (aftershock statistics follow the
Omori decay), verified shaking reports, and building vulnerability. Risk is
"continued strong shaking / damage accumulation", not a day-of-quake forecast.

Telemetry arrives through the IngestedDatum archive (seismic_energy, ground_accel)
so the canonical weather tables stay untouched.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _eq_probability(components: dict[str, float]) -> float:
    signal = (
        1.0 * components.get("ground_accel", 0)
        + 1.2 * components.get("energy_release", 0)
        + 0.7 * components.get("building_vulnerability", 0)
        + 0.5 * components.get("shaking_reports", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=44.0)


def _latest_seismic(payload: dict) -> dict:
    rows = payload.get("seismic") or []
    latest = rows[-1] if rows else {}
    window = rows[-12:] if rows else []
    energy = sum(r.get("value", 0) for r in window if r.get("metric") == "seismic_energy")
    return {
        "accel": float(latest.get("value", 0) if latest.get("metric") == "ground_accel" else 0),
        "energy": float(energy),
        "fresh": bool(rows),
    }


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    citizen = agg.get("citizen_report", {})
    se = _latest_seismic(payload)
    exposure = payload.get("exposure", 1.0)
    population = payload.get("population", 0)

    accel_g = se["accel"] if se["fresh"] else 0.0  # ground_accel stored in g-units
    return {
        "ground_accel": _clip(accel_g * 14.0),
        "energy_release": _clip(se["energy"] / 40.0),
        "building_vulnerability": _clip((exposure + (population / 2_000_000)) * 2.4),
        "shaking_reports": _clip(citizen.get("citizen_pressure", 0) * 2.4),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for r in (payload.get("seismic") or [])[-48:]:
        out.append(
            {
                "ground_accel": _clip(r["value"] * 14.0) if r.get("metric") == "ground_accel" else 0.0,
                "energy_release": _clip(r["value"] / 40.0) if r.get("metric") == "seismic_energy" else 0.0,
                "building_vulnerability": 3.0,
                "shaking_reports": 0.5,
            }
        )
    return out


def _eq_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    # evolution path has no seismic rows — drive on exposure floor + soil proxy
    return {
        "ground_accel": _clip(soil * 0.8),
        "energy_release": _clip(3.0 + (12.0 - soil) * 0.4),
        "building_vulnerability": _clip((exposure + 0.5) * 2.4),
        "shaking_reports": _clip((12.0 - soil) * 0.5),
    }


def _eq_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {
            "id": "energy",
            "label": "Energy release (seismic)",
            "kind": "cause",
            "value": f"{components.get('energy_release', 0) * 40:.0f} GJ window",
            "confidence": 0.85,
        },
        {
            "id": "accel",
            "label": "Peak ground accel",
            "kind": "mechanism",
            "value": f"{components.get('ground_accel', 0) / 14:.2f} g",
            "confidence": 0.9,
        },
        {
            "id": "vuln",
            "label": "Building vulnerability",
            "kind": "condition",
            "value": f"{components.get('building_vulnerability', 0):.2f}/12",
            "confidence": 0.75,
        },
        {
            "id": "shake",
            "label": "Verified shaking reports",
            "kind": "condition",
            "value": f"{components.get('shaking_reports', 0):.1f} reports",
            "confidence": 0.6,
        },
        {
            "id": "risk",
            "label": f"Seismic episode risk ({pred.get('risk_probability', 0):.0%})",
            "kind": "risk",
            "value": f"severity {pred.get('severity', 0):.1f}/5",
            "confidence": pred.get("confidence", 0.5),
        },
    ]
    edges = [
        {"source": "energy", "target": "accel", "label": "energy release → ground motion"},
        {"source": "accel", "target": "risk", "label": "strong shaking drives damage"},
        {"source": "energy", "target": "shake", "label": "aftershock sequence sustains reports"},
        {"source": "vuln", "target": "risk", "label": "unreinforced stock amplifies losses"},
        {"source": "shake", "target": "risk", "label": "verified surface impact"},
    ]
    return {"nodes": nodes, "edges": edges}


def _eq_recommend(p: float, sev: float) -> list:
    return [
        {
            "id": "rec_eq_1",
            "stakeholder": "responders",
            "priority": 1 if p > 0.6 else 2,
            "action": "Stand up structural assessment teams along the high-energy release arc.",
            "reasoning": "aftershock damage accumulates fastest near peak energy release.",
            "evidence_ids": [],
        },
        {
            "id": "rec_eq_2",
            "stakeholder": "civic",
            "priority": 1 if sev >= 3 else 2,
            "action": "Hold safe-zone protocols; keep evacuation lanes clear of the vulnerable stock.",
            "reasoning": "unreinforced buildings dominate life exposure in sustained sequences.",
            "evidence_ids": [],
        },
        {
            "id": "rec_eq_3",
            "stakeholder": "utilities",
            "priority": 2,
            "action": "Inspect lifelines (gas, power) at the shaking epicentre before re-energizing.",
            "reasoning": "post-quake utility ignitions are the second-order kill.",
            "evidence_ids": [],
        },
        {
            "id": "rec_eq_4",
            "stakeholder": "public",
            "priority": 3,
            "action": "Report verified shaking so the energy-release map stays live.",
            "reasoning": "ground truth sharpens the episode envelope faster than instrumentation.",
            "evidence_ids": [],
        },
    ]


EARTHQUAKE = HazardSpec(
    id="earthquake",
    label="Earthquake",
    fusion=_fusion,
    history=_historical,
    formula=_eq_probability,
    features={
        "ground_accel": "peak ground accel",
        "energy_release": "energy release",
        "building_vulnerability": "building vulnerability",
        "shaking_reports": "verified shaking reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {
            "id": "structural_survey",
            "name": "Structural Survey",
            "kind": "operational",
            "description": "Post-shaking assessment of unreinforced building stock",
        },
        {
            "id": "safe_zone_holding",
            "name": "Safe Zone Holding",
            "kind": "policy",
            "description": "Keep public in designated open safe zones during sequences",
        },
        {
            "id": "lifeline_inspection",
            "name": "Lifeline Inspection",
            "kind": "engineering",
            "description": "Gas/power inspection before re-energizing",
        },
        {
            "id": "tsunami_standby",
            "name": "Coastal Tsunami Standby",
            "kind": "operational",
            "description": "Hold coastal low-ground alert while energy release is high",
        },
        {
            "id": "retrofit_queue",
            "name": "Retrofit Queue",
            "kind": "engineering",
            "description": "Prioritize vulnerable blocks for structural retrofit",
        },
    ],
    evidence=[
        EvidenceTemplate(
            "usgs-seismic", "observation", "peak ground acceleration above the damage threshold", "ground_accel", 2
        ),
        EvidenceTemplate(
            "usgs-seismic",
            "observation",
            "sustained energy release consistent with an active sequence",
            "energy_release",
            3,
        ),
        EvidenceTemplate(
            "civic-reports", "report", "verified shaking reports from the metropolitan area", "shaking_reports", 1
        ),
        EvidenceTemplate("news-eom", "citation", "seismic episode advisory active for the region", None, 6),
    ],
    hourly=_eq_hourly,
    causal=_eq_causal,
    recommend=_eq_recommend,
    scale=44.0,
)
