"""Hazard templates — the per-hazard contract for the core engine.

A HazardSpec declares everything the region-agnostic core needs to run a
hazard: which sensor features to fuse and how, the risk formula, alert
thresholds, explanation graph, recommendations, evidence templates and
intervention catalog. Adding a hazard = adding one spec + seed telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

Fusion = Callable[[dict], dict[str, float]]
History = Callable[[dict], list[dict[str, float]]]
Hourly = Callable[[list[dict], float, float, float], dict[str, float]]  # (weather_window, soil, exposure, cap)
Causal = Callable[[dict[str, float], dict], dict]  # (components, prediction) → {nodes, edges}
Recommend = Callable[[float, float], list]  # (probability, severity) → recommendations


@dataclass
class EvidenceTemplate:
    source_id: str
    kind: str  # observation | forecast | report | citation
    description: str
    feature_key: str | None
    hours_ago: int = 3


@dataclass
class HazardSpec:
    id: str
    label: str  # "flood", "wildfire", ...
    fusion: Fusion
    history: History
    formula: Callable[[dict[str, float]], float]
    features: dict[str, str] = field(default_factory=dict)  # component key → human label
    thresholds: dict[str, float] = field(default_factory=dict)  # level → min probability
    interventions: list[dict] = field(default_factory=list)  # id/name/kind/description
    evidence: list[EvidenceTemplate] = field(default_factory=list)
    hourly: Hourly | None = None  # per-hour components for the evolution curve
    causal: Causal | None = None
    recommend: Recommend | None = None
    scale: float = 52.0

    def level(self, p: float) -> str:
        """Map probability → level using this hazard's thresholds."""
        for name, cutoff in [("critical", self.thresholds.get("critical", 0.75)),
                             ("high", self.thresholds.get("high", 0.55)),
                             ("moderate", self.thresholds.get("moderate", 0.3))]:
            if p >= cutoff:
                return name
        return "low"

    def probability(self, components: dict[str, float]) -> float:
        return self.formula(components)

    def component_labels(self) -> dict[str, str]:
        return self.features

    def intervention_map(self) -> dict[str, dict]:
        return {i["id"]: i for i in self.interventions}