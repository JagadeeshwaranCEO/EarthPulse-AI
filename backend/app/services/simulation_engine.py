"""What-if simulation engine.

A transparent water-balance/hazard model: risk probability responds to drainage
stress, headroom, and rainfall — interventions (pump pre-positioning, reservoir
release, drainage clearing, sandbagging, evacuation) shift these inputs by a
physical-ish transfer. Deterministic, instant, explainable. No LLM in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from app.ml.forecaster import DEFAULT_FORECASTER

# intervention_id -> (targets, description)
_INTERVENTIONS: dict[str, tuple[dict[str, float], str]] = {
    "pump_preposition": (
        {"drainage_stress": -4.0, "headroom_deficit": -2.0},
        "Pre-position high-capacity pumps at low-lying wards; increases effective drainage throughput.",
    ),
    "reservoir_release": (
        {"headroom_deficit": -3.5, "rain_intensity": -0.5},
        "Coordinated reservoir release ahead of peak inflow to create storage headroom.",
    ),
    "drainage_clearing": (
        {"drainage_stress": -3.0},
        "Clear stormwater inlets and canals (desilting crews + civic task force).",
    ),
    "sandbagging": (
        {"headroom_deficit": -2.5, "soil_moisture": -0.8},
        "Sandbag low-lying entrances and river-adjacent blocks.",
    ),
    "evacuation_ready": (
        {"citizen_pressure": -1.5},
        "Stage shelters and announce evacuation routes to high-risk wards.",
    ),
    "rainwater_harvesting": (
        {"drainage_stress": -1.5, "soil_moisture": -1.0},
        "Activate rooftop harvesting and retention basins to shave peak runoff.",
    ),
}

_INTERVENTION_META: dict[str, dict] = {
    "pump_preposition": {"kind": "operational", "cost_index": 0.6, "carbon_kg": 320.0},
    "reservoir_release": {"kind": "operational", "cost_index": 0.4, "carbon_kg": 40.0},
    "drainage_clearing": {"kind": "engineering", "cost_index": 0.5, "carbon_kg": 210.0},
    "sandbagging": {"kind": "engineering", "cost_index": 0.3, "carbon_kg": 90.0},
    "evacuation_ready": {"kind": "policy", "cost_index": 0.2, "carbon_kg": 25.0},
    "rainwater_harvesting": {"kind": "policy", "cost_index": 0.7, "carbon_kg": 140.0},
}


@dataclass
class BaselineState:
    probability: float
    severity: float
    expected_damage_usd: float
    components: dict[str, float]


def available_interventions() -> list[dict]:
    return [
        {
            "id": iid,
            "name": iid.replace("_", " ").title(),
            "description": desc,
            **_INTERVENTION_META[iid],
        }
        for iid, (_, desc) in _INTERVENTIONS.items()
    ]


def _probability(components: dict[str, float]) -> float:
    from app.ml.forecaster import probability_from_components

    return probability_from_components(components)


def _severity(p: float) -> float:
    return float(np.clip(p * 5.0, 0.0, 5.0))


def _damage_m(p: float, population: int) -> float:
    return round(float(p * population * 2.2), 1)  # ~$2.2 direct cost per affected resident at p=1


def baseline(components: dict[str, float], population: int) -> BaselineState:
    p = _probability(components)
    return BaselineState(
        probability=p,
        severity=_severity(p),
        expected_damage_usd=_damage_m(p, population),
        components=dict(components),
    )


def run_simulation(
    components: dict[str, float],
    population: int,
    interventions: dict[str, float],
) -> dict:
    """interventions: {id: intensity 0..1}. Returns before/after + deltas + carbon ledger."""
    before = baseline(components, population)

    after_components = dict(components)
    effects: list[dict] = []
    for iid, intensity in interventions.items():
        if intensity <= 0 or iid not in _INTERVENTIONS:
            continue
        targets, desc = _INTERVENTIONS[iid]
        for key, delta in targets.items():
            after_components[key] = max(0.0, after_components.get(key, 0) + delta * intensity)
        effects.append({"intervention": iid, "intensity": round(intensity, 2), "description": desc})

    after = baseline(after_components, population)

    damage_avoided = before.expected_damage_usd - after.expected_damage_usd
    probability_reduction = before.probability - after.probability
    carbon_spent = sum(_INTERVENTION_META[i].get("carbon_kg", 0) * int for i, int in interventions.items() if i in _INTERVENTION_META)
    co2e_avoided_kg = damage_avoided * 0.52  # ~520 t CO2e per $1M damage avoided

    return {
        "id": f"sim_{uuid4().hex[:10]}",
        "baseline": {
            "probability": round(before.probability, 3),
            "severity": round(before.severity, 2),
            "expected_damage_usd": before.expected_damage_usd,
            "components": before.components,
        },
        "after": {
            "probability": round(after.probability, 3),
            "severity": round(after.severity, 2),
            "expected_damage_usd": after.expected_damage_usd,
            "components": after_components,
        },
        "deltas": {
            "probability_reduction": round(probability_reduction, 3),
            "severity_reduction": round(before.severity - after.severity, 2),
            "damage_avoided_usd": round(damage_avoided, 1),
            "damage_reduction_pct": round((damage_avoided / before.expected_damage_usd * 100) if before.expected_damage_usd > 0 else 0.0, 1),
        },
        "effects": effects,
        "carbon_ledger": {
            "carbon_spent_kg": round(carbon_spent, 1),
            "co2e_avoided_kg": round(co2e_avoided_kg, 1),
            "net_kg": round(co2e_avoided_kg - carbon_spent, 1),
            "method": "damage_avoidance_estimation; demo-grade estimate, not verified offset",
        },
    }
