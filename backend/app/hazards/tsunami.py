"""Tsunami template — sea-disturbance early warning.

Models the actionable lead window after an offshore seismic trigger: seismic
energy release feeding a sea-surface disturbance (satellite surface-water
anomaly), coastal exposure, and verified sea-state reports (recession /
standing water). Honest framing: this is an early-warning / response-readiness
model over the hours a surge takes to reach shore, not a far-field forecast.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _tsu_probability(components: dict[str, float]) -> float:
    signal = (
        1.2 * components.get("sea_disturbance", 0)
        + 1.0 * components.get("source_energy", 0)
        + 0.8 * components.get("coastal_exposure", 0)
        + 0.5 * components.get("sea_state_report", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=46.0)


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})
    exposure = payload.get("exposure", 1.0)
    seismic_rows = payload.get("seismic") or []
    window = seismic_rows[-12:] if seismic_rows else []
    energy = sum(r.get("value", 0) for r in window if r.get("metric") == "seismic_energy")

    swi = sat.get("surface_water_index", 0)
    return {
        "sea_disturbance": _clip(swi * 4.5 + energy / 80.0),
        "source_energy": _clip(energy / 30.0),
        "coastal_exposure": _clip(exposure * 3.4),
        "sea_state_report": _clip(citizen.get("citizen_pressure", 0) * 2.6),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for r in (payload.get("seismic") or [])[-48:]:
        out.append({
            "sea_disturbance": _clip(r["value"] / 30.0) if r.get("metric") == "seismic_energy" else 0.0,
            "source_energy": _clip(r["value"] / 30.0) if r.get("metric") == "seismic_energy" else 0.0,
            "coastal_exposure": 4.0,
            "sea_state_report": 0.5,
        })
    return out


def _tsu_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    return {
        "sea_disturbance": _clip(soil * 0.9),
        "source_energy": _clip(2.0 + (12.0 - soil) * 0.3),
        "coastal_exposure": _clip(exposure * 3.4),
        "sea_state_report": _clip((12.0 - soil) * 0.5),
    }


def _tsu_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "src", "label": "Offshore seismic energy", "kind": "cause",
         "value": f"{components.get('source_energy', 0) * 30:.0f} GJ", "confidence": 0.85},
        {"id": "sea", "label": "Sea-surface disturbance", "kind": "mechanism",
         "value": f"{components.get('sea_disturbance', 0):.2f}/12", "confidence": 0.8},
        {"id": "coast", "label": "Coastal surge exposure", "kind": "condition",
         "value": f"{components.get('coastal_exposure', 0):.2f}/12", "confidence": 0.75},
        {"id": "report", "label": "Sea-state reports", "kind": "condition",
         "value": f"{components.get('sea_state_report', 0):.1f} reports", "confidence": 0.6},
        {"id": "risk", "label": f"Tsunami risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "src", "target": "sea", "label": "sea-floor displacement"},
        {"source": "sea", "target": "risk", "label": "surge reaches the low coastal reach"},
        {"source": "coast", "target": "risk", "label": "low-ground wards flood first"},
        {"source": "report", "target": "sea", "label": "observed recession precedes surge"},
        {"source": "report", "target": "risk", "label": "ground truth sharpens the envelope"},
    ]
    return {"nodes": nodes, "edges": edges}


def _tsu_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_tsu_1", "stakeholder": "responders", "priority": 1 if p > 0.6 else 2,
         "action": "Hold coastal low-ground clear; move rescue assets to high-ground staging.",
         "reasoning": "the surge window is compressed — staging must precede the wave.",
         "evidence_ids": []},
        {"id": "rec_tsu_2", "stakeholder": "civic", "priority": 1 if sev >= 3 else 2,
         "action": "Execute shoreline evacuation to the 30 m contour on the disturbed arc.",
         "reasoning": "life exposure concentrates in the first surge corridor.",
         "evidence_ids": []},
        {"id": "rec_tsu_3", "stakeholder": "utilities", "priority": 2,
         "action": "Isolate coastal substations before water reaches the corridor.",
         "reasoning": "energized infrastructure in the surge zone is a secondary hazard.",
         "evidence_ids": []},
        {"id": "rec_tsu_4", "stakeholder": "public", "priority": 3,
         "action": "Report sea recession or standing water immediately from high ground.",
         "reasoning": "recession observations validate the surge envelope before impact.",
         "evidence_ids": []},
    ]


TSUNAMI = HazardSpec(
    id="tsunami",
    label="Tsunami",
    fusion=_fusion,
    history=_historical,
    formula=_tsu_probability,
    features={
        "sea_disturbance": "sea-surface disturbance",
        "source_energy": "offshore seismic energy",
        "coastal_exposure": "coastal surge exposure",
        "sea_state_report": "sea-state reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {"id": "shoreline_evacuation", "name": "Shoreline Evacuation", "kind": "policy",
         "description": "Evacuate the surge corridor to high-ground contour"},
        {"id": "high_ground_staging", "name": "High-Ground Staging", "kind": "operational",
         "description": "Move rescue assets behind the surge line"},
        {"id": "coastal_substation_isolation", "name": "Coastal Grid Isolation", "kind": "engineering",
         "description": "Isolate coastal substations ahead of water arrival"},
        {"id": "tide_gauge_monitoring", "name": "Tide Gauge Monitoring", "kind": "operational",
         "description": "Hold continuous tide-gauge and buoy telemetry watch"},
        {"id": "coastal_zoning", "name": "Coastal Zoning", "kind": "policy",
         "description": "Restrict new construction inside the surge corridor"},
    ],
    evidence=[
        EvidenceTemplate("usgs-seismic", "observation",
                         "offshore seismic energy consistent with sea-floor displacement",
                         "source_energy", 2),
        EvidenceTemplate("gpm-nasa", "observation",
                         "surface-water disturbance ahead of the shore",
                         "sea_disturbance", 2),
        EvidenceTemplate("civic-reports", "report",
                         "reported sea recession or standing water along the shore",
                         "sea_state_report", 1),
        EvidenceTemplate("news-eom", "citation",
                         "tsunami advisory active for the coastal district",
                         None, 6),
    ],
    hourly=_tsu_hourly,
    causal=_tsu_causal,
    recommend=_tsu_recommend,
    scale=46.0,
)
