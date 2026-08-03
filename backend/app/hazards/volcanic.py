"""Volcanic template — unrest / eruption-warning model.

Volcano risk is monitored, not forecast: tremor amplitude, SO2 flux and ash
plume height are the standard precursor telemetry; verified ashfall reports
anchor ground truth. Components flow through the IngestedDatum archive
(volcanic_tremor, so2_flux, ash_plume_km) plus satellite and citizen streams.
"""

from __future__ import annotations

from app.hazards.spec import EvidenceTemplate, HazardSpec
from app.ml.forecaster import DEFAULT_FORECASTER


def _clip(v: float) -> float:
    return min(12.0, max(0.0, float(v)))


def _vol_probability(components: dict[str, float]) -> float:
    signal = (
        1.1 * components.get("tremor_amplitude", 0)
        + 1.0 * components.get("so2_flux", 0)
        + 0.8 * components.get("ash_plume", 0)
        + 0.6 * components.get("ashfall_report", 0)
    )
    return DEFAULT_FORECASTER.to_probability(signal, scale=46.0)


def _latest_volc(payload: dict) -> dict:
    rows = payload.get("seismic") or []
    latest = {}
    for r in reversed(rows):
        latest.setdefault(r.get("metric"), r.get("value", 0))
    return latest


def _fusion(payload: dict) -> dict[str, float]:
    agg = payload.get("agent_outputs") or {}
    sat = agg.get("satellite", {})
    citizen = agg.get("citizen_report", {})
    v = _latest_volc(payload)

    thermal_proxy = 12.0 - sat.get("soil_moisture_anomaly", 6) * 1.5
    return {
        "tremor_amplitude": _clip(v.get("volcanic_tremor", 0) * 6.0),
        "so2_flux": _clip(v.get("so2_flux", 0) * 2.4),
        "ash_plume": _clip(v.get("ash_plume_km", 0) * 1.2),
        "ashfall_report": _clip(citizen.get("citizen_pressure", 0) * 2.4 + thermal_proxy * 0.15),
    }


def _historical(payload: dict) -> list[dict[str, float]]:
    out = []
    for r in (payload.get("seismic") or [])[-48:]:
        metric = r.get("metric")
        out.append({
            "tremor_amplitude": _clip(r["value"] * 6.0) if metric == "volcanic_tremor" else 0.0,
            "so2_flux": _clip(r["value"] * 2.4) if metric == "so2_flux" else 0.0,
            "ash_plume": _clip(r["value"] * 1.2) if metric == "ash_plume_km" else 0.0,
            "ashfall_report": 0.4,
        })
    return out


def _vol_hourly(window: list[dict], soil: float, exposure: float, cap: float) -> dict[str, float]:
    return {
        "tremor_amplitude": _clip(2.0 + (12.0 - soil) * 0.4),
        "so2_flux": _clip(1.5 + (12.0 - soil) * 0.3),
        "ash_plume": _clip(1.0 + (12.0 - soil) * 0.25),
        "ashfall_report": _clip((12.0 - soil) * 0.4),
    }


def _vol_causal(components: dict[str, float], pred: dict) -> dict:
    nodes = [
        {"id": "tremor", "label": "Volcanic tremor", "kind": "cause",
         "value": f"{components.get('tremor_amplitude', 0):.2f}/12", "confidence": 0.9},
        {"id": "so2", "label": "SO2 flux", "kind": "mechanism",
         "value": f"{components.get('so2_flux', 0):.1f} kt/d", "confidence": 0.85},
        {"id": "plume", "label": "Ash plume height", "kind": "mechanism",
         "value": f"{components.get('ash_plume', 0):.1f} km", "confidence": 0.8},
        {"id": "ash", "label": "Verified ashfall reports", "kind": "condition",
         "value": f"{components.get('ashfall_report', 0):.1f} reports", "confidence": 0.6},
        {"id": "risk", "label": f"Volcanic risk ({pred.get('risk_probability', 0):.0%})", "kind": "risk",
         "value": f"severity {pred.get('severity', 0):.1f}/5", "confidence": pred.get("confidence", 0.5)},
    ]
    edges = [
        {"source": "tremor", "target": "risk", "label": "magmatic movement"},
        {"source": "tremor", "target": "so2", "label": "degassing with ascent"},
        {"source": "so2", "target": "plume", "label": "plume height tracks flux"},
        {"source": "plume", "target": "ash", "label": "plume collapse → ashfall"},
        {"source": "ash", "target": "risk", "label": "surface impact confirmed"},
    ]
    return {"nodes": nodes, "edges": edges}


def _vol_recommend(p: float, sev: float) -> list:
    return [
        {"id": "rec_vol_1", "stakeholder": "responders", "priority": 1 if p > 0.6 else 2,
         "action": "Raise the alert level on the exclusion radius; stage ash-rescue teams.",
         "reasoning": "tremor and flux coupling is the standard pre-eruption signature.",
         "evidence_ids": []},
        {"id": "rec_vol_2", "stakeholder": "civic", "priority": 1 if sev >= 3 else 2,
         "action": "Close the crater-approach corridor; protect shelter stock from ash load.",
         "reasoning": "ash load collapses roofs within the fall zone.",
         "evidence_ids": []},
        {"id": "rec_vol_3", "stakeholder": "utilities", "priority": 2,
         "action": "Protect water intakes and distribution from ash contamination.",
         "reasoning": "ash-laden runoff poisons supply within hours.",
         "evidence_ids": []},
        {"id": "rec_vol_4", "stakeholder": "public", "priority": 3,
         "action": "Report ashfall thickness and gas odour from safe distance.",
         "reasoning": "ground truth anchors plume and flux interpretation.",
         "evidence_ids": []},
    ]


VOLCANIC = HazardSpec(
    id="volcanic",
    label="Volcanic",
    fusion=_fusion,
    history=_historical,
    formula=_vol_probability,
    features={
        "tremor_amplitude": "volcanic tremor",
        "so2_flux": "SO2 flux",
        "ash_plume": "ash plume height",
        "ashfall_report": "verified ashfall reports",
    },
    thresholds={"critical": 0.8, "high": 0.6, "moderate": 0.35},
    interventions=[
        {"id": "exclusion_radius", "name": "Exclusion Radius", "kind": "policy",
         "description": "Enforce crater-approach exclusion and corridor closure"},
        {"id": "ash_rescue_teams", "name": "Ash Rescue Teams", "kind": "operational",
         "description": "Stage teams for the fall zone"},
        {"id": "ash_load_shelters", "name": "Ash-Load Shelter", "kind": "engineering",
         "description": "Reinforce shelters against ash load"},
        {"id": "water_protection", "name": "Water Protection", "kind": "engineering",
         "description": "Protect intakes from ash contamination"},
        {"id": "gas_monitoring", "name": "Gas Monitoring", "kind": "operational",
         "description": "Continuous SO2/CO2 flux monitoring"},
    ],
    evidence=[
        EvidenceTemplate("usgs-seismic", "observation",
                         "volcanic tremor amplitude above the unrest threshold",
                         "tremor_amplitude", 2),
        EvidenceTemplate("gpm-nasa", "observation",
                         "SO2 flux and plume height elevation",
                         "so2_flux", 3),
        EvidenceTemplate("civic-reports", "report",
                         "verified ashfall and gas odour reports",
                         "ashfall_report", 1),
        EvidenceTemplate("news-eom", "citation",
                         "volcano alert level raised for the region",
                         None, 6),
    ],
    hourly=_vol_hourly,
    causal=_vol_causal,
    recommend=_vol_recommend,
    scale=46.0,
)
