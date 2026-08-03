"""Environmental Memory — historical analogue engine.

Each zone carries a memory profile: past inundation events (count over 10 years,
known vulnerabilities, choke points). The current live feature state is compared
against stored event signatures (normalized inverse euclidean → similarity 0..1)
so EarthPulse can say *"this pattern resembles December 2015 at 84%"* — computed,
not narrated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class HistoricalEvent:
    name: str
    date: str
    severity: int  # 0..5
    signature: dict[str, float]  # feature → typical magnitude
    description: str = ""


@dataclass
class ZoneMemory:
    location_id: str
    floods_10y: int
    vulnerabilities: list[str]
    choke_points: list[str]
    events: list[HistoricalEvent] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)  # structural changes since the analogue event


# Feature order used for vector similarity
_FEATURES = ["rain_intensity", "soil_moisture", "headroom_deficit", "drainage_stress"]

# Per-zone memory store (seeded, provenance-tagged in the API layer)
_MEMORY: dict[str, ZoneMemory] = {
    "velachery": ZoneMemory(
        "velachery", floods_10y=6,
        vulnerabilities=["Velachery lake overflow", "low-lying residential basin"],
        choke_points=["South Buckingham Canal intersection", "Velachery main road culvert"],
        divergences=[
            "Urban permeability in this basin decreased ~14% since 2015 (new construction) — runoff response is faster today",
            "Reservoir pre-discharge protocols have lowered base basin levels by ~1.2 m vs 2015",
        ],
        events=[
            HistoricalEvent("Chennai Floods", "Dec 2015", 5, {"rain_intensity": 11.0, "soil_moisture": 9.5, "headroom_deficit": 10.0, "drainage_stress": 10.5}, "compound cyclonic inundation"),
            HistoricalEvent("NE monsoon inundation", "Nov 2021", 4, {"rain_intensity": 9.5, "soil_moisture": 8.5, "headroom_deficit": 8.0, "drainage_stress": 9.0}, "back-to-back rain spells"),
            HistoricalEvent("Urban flash flood", "Nov 2023", 3, {"rain_intensity": 9.0, "soil_moisture": 6.0, "headroom_deficit": 7.5, "drainage_stress": 8.5}, "high-intensity short-duration event"),
        ],
    ),
    "mylapore": ZoneMemory(
        "mylapore", floods_10y=4,
        vulnerabilities=["Coastal ward storm surge coupling", "aged stormwater network"],
        choke_points=["Mylapore tank outlet", "Luz church road drain"],
        divergences=[
            "Coastal armoring added along the marina reach — surge coupling reduced vs 2015",
            "Aged stormwater network now flows into the restored Mylapore tank (better buffer, slower outflow)",
        ],
        events=[
            HistoricalEvent("Chennai Floods", "Dec 2015", 5, {"rain_intensity": 10.5, "soil_moisture": 9.0, "headroom_deficit": 9.5, "drainage_stress": 10.0}, "compound cyclonic inundation"),
            HistoricalEvent("NE monsoon inundation", "Nov 2021", 3, {"rain_intensity": 8.5, "soil_moisture": 7.0, "headroom_deficit": 7.0, "drainage_stress": 7.5}, "tidal coupling"),
        ],
    ),
    "north_chennai": ZoneMemory(
        "north_chennai", floods_10y=7,
        vulnerabilities=["Extremely low elevation", "dense informal settlements", "industrial water-logging"],
        choke_points=["Otteri Nullah segment", "Buckingham Canal north reach"],
        divergences=[
            "Otteri Nullah widened ~30% under the 2020–2024 flood-mitigation program — faster drain-off",
            "Industrial water-logging exposure raised by new logistics hubs near the canal",
        ],
        events=[
            HistoricalEvent("Chennai Floods", "Dec 2015", 5, {"rain_intensity": 11.0, "soil_moisture": 9.8, "headroom_deficit": 10.5, "drainage_stress": 11.0}, "compound cyclonic inundation"),
            HistoricalEvent("NE monsoon inundation", "Nov 2021", 4, {"rain_intensity": 9.0, "soil_moisture": 8.8, "headroom_deficit": 8.8, "drainage_stress": 9.5}, "drainage network overwhelmed"),
        ],
    ),
}

# Generic profiles for zones without bespoke memory
_GENERIC_EVENTS = [
    HistoricalEvent("Chennai Floods", "Dec 2015", 5, {"rain_intensity": 10.8, "soil_moisture": 9.4, "headroom_deficit": 10.0, "drainage_stress": 10.5}, "compound cyclonic inundation"),
    HistoricalEvent("NE monsoon inundation", "Nov 2021", 4, {"rain_intensity": 9.2, "soil_moisture": 8.2, "headroom_deficit": 8.2, "drainage_stress": 8.8}, "monsoon onset saturation"),
]

_GENERIC_VULN = ["stormwater network at design limit", "low-lying street flooding"]
_GENERIC_CHOKE = ["primary drain outfall", "river-adjacent culvert"]
_GENERIC_DIVERGENCES = [
    "Reservoir pre-discharge protocols lowered base basin levels ~1.2 m vs 2015",
    "Stormwater network upgraded in patches since 2015 — coverage is uneven",
]


def memory_for(zone_id: str) -> ZoneMemory:
    mem = _MEMORY.get(zone_id)
    if mem:
        return mem
    return ZoneMemory(zone_id, floods_10y=3, vulnerabilities=list(_GENERIC_VULN),
                      choke_points=list(_GENERIC_CHOKE), events=list(_GENERIC_EVENTS),
                      divergences=list(_GENERIC_DIVERGENCES))


def _vec(comps: dict[str, float]) -> list[float]:
    return [comps.get(f, 0.0) for f in _FEATURES]


def _similarity(a: list[float], b: list[float]) -> float:
    """Inverse normalized euclidean → 0..1 (1 = identical signature)."""
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return float(max(0.0, min(1.0, 1.0 - d / 14.0)))


def analogue_matches(zone_id: str, components: dict[str, float]) -> list[dict]:
    """Top historical analogues for the current feature state."""
    mem = memory_for(zone_id)
    vec = _vec(components)
    scored = [
        {"event": e.name, "date": e.date, "severity": e.severity,
         "similarity": round(_similarity(vec, _vec(e.signature)), 3),
         "description": e.description}
        for e in mem.events
    ]
    return sorted(scored, key=lambda s: -s["similarity"])


_DRIVER_LABELS = {
    "rain_intensity": "Rainfall intensity",
    "soil_moisture": "Soil saturation",
    "headroom_deficit": "Drainage headroom",
    "drainage_stress": "Drainage overload",
    "citizen_pressure": "Ground reports",
}

_DRIVER_KEYS = ["rain_intensity", "soil_moisture", "headroom_deficit", "drainage_stress"]


def _matching_drivers(components: dict[str, float], signature: dict[str, float]) -> list[dict]:
    """Which causal drivers line up with the analogue event (within 70% of its signature)."""
    out = []
    for k in _DRIVER_KEYS:
        cur = components.get(k, 0.0)
        ref = signature.get(k, 0.0)
        ratio = cur / ref if ref > 0 else 0.0
        out.append({
            "driver": _DRIVER_LABELS[k],
            "feature": k,
            "current": round(cur, 2),
            "analogue": ref,
            "matched": ratio >= 0.7,
        })
    return out


def _reliability(components: dict[str, float], signature: dict[str, float],
                 similarity: float, divergences: list[str]) -> str:
    """Analogue reliability: pattern overlap minus structural drift."""
    matched = sum(1 for d in _matching_drivers(components, signature) if d["matched"])
    base = similarity
    # structural drift discounts reliability
    drift_penalty = min(0.25, 0.08 * len(divergences))
    score = base - drift_penalty + 0.06 * matched
    if score >= 0.75:
        return "High"
    if score >= 0.5:
        return "Moderate"
    return "Low"


def memory_view(zone_id: str, components: dict[str, float]) -> dict:
    mem = memory_for(zone_id)
    matches = analogue_matches(zone_id, components)
    top = matches[0] if matches else None
    top_event = next((e for e in mem.events if top and e.name == top["event"] and e.date == top["date"]), None)
    drivers = _matching_drivers(components, top_event.signature) if top_event else []
    reliability = _reliability(components, top_event.signature, top["similarity"], mem.divergences) if top_event else "Low"
    return {
        "zone_id": zone_id,
        "historical_floods_10y": mem.floods_10y,
        "known_vulnerabilities": mem.vulnerabilities,
        "choke_points": mem.choke_points,
        "top_analogues": matches,
        "headline": (
            f"{mem.floods_10y} major inundation events in the past decade; current telemetry "
            f"resembles {top['event']} ({top['date']}) at {top['similarity'] * 100:.0f}%"
            if top else "no strong historical analogue"
        ),
        "analogue_breakdown": {
            "closest_event": top["event"] if top else None,
            "closest_date": top["date"] if top else None,
            "similarity": top["similarity"] if top else 0.0,
            "matching_drivers": drivers,
            "critical_divergences": mem.divergences,
            "estimated_reliability": reliability,
        } if top else None,
    }
