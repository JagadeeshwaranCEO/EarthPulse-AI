"""Permutation feature attribution — dependency-free stand-in for SHAP.

Shifts each risk-driving feature by ±1σ and measures the resulting change in the
forecasted probability. Direction tells whether the feature raises or lowers risk.
SHAP itself can be swapped in behind this same return type.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ml.forecaster import probability_from_components


@dataclass
class AttributionItem:
    feature: str
    influence: float  # 0..1 relative importance
    direction: str  # raises | lowers
    description: str = ""


def _risk_inputs(components: dict[str, float]) -> dict[str, float]:
    """Map named components to the forecaster's feature space."""
    return {
        "rain_intensity": components.get("rain_intensity", 0.0),
        "soil_moisture": components.get("soil_moisture", 0.0),
        "headroom_deficit": components.get("headroom_deficit", 0.0),
        "drainage_stress": components.get("drainage_stress", 0.0),
        "citizen_pressure": components.get("citizen_pressure", 0.0),
    }


def compute_attribution(components: dict[str, float]) -> list[AttributionItem]:
    base = _risk_inputs(components)
    base_score = _probability_from_features(base)
    items: list[AttributionItem] = []
    for feature, value in base.items():
        perturbed = dict(base)
        perturbed[feature] = value + 1.0
        delta = _probability_from_features(perturbed) - base_score
        items.append(
            AttributionItem(
                feature=feature,
                influence=abs(delta),
                direction="raises" if delta > 0 else "lowers",
                description=_describe(feature, delta),
            )
        )
    total = sum(i.influence for i in items) or 1.0
    for i in items:
        i.influence = round(i.influence / total, 3)
    items.sort(key=lambda i: -i.influence)
    return items


def _probability_from_features(f: dict[str, float]) -> float:

    return probability_from_components(f)


def _describe(feature: str, delta: float) -> str:
    if feature == "rain_intensity":
        return "accumulated rainfall intensity driving the onset"
    if feature == "soil_moisture":
        return "pre-saturated soil reduces absorption capacity"
    if feature == "headroom_deficit":
        return "distance between water level and drainage capacity"
    if feature == "drainage_stress":
        return "stormwater network load vs design capacity"
    if feature == "citizen_pressure":
        return "verified ground reports of waterlogging"
    return f"feature {feature} {'raises' if delta > 0 else 'lowers'} risk"
