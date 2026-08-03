"""Environmental Memory — historical analogue engine.

Each zone carries a memory profile: past disaster events (count over 10 years,
known vulnerabilities, choke points). The current live feature state is compared
against stored event signatures (normalized inverse euclidean → similarity 0..1)
so EarthPulse can say *"this pattern resembles December 2015 at 84%"* — computed,
not narrated. Profiles are hazard-typed: a wildfire zone matches wildfire
signatures (fuel dryness, wind kick, thermal anomaly), a flood zone matches
inundation signatures. Unknown zones fall back to hazard-generic event records.
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
    hazard: str = "flood"


@dataclass
class ZoneMemory:
    location_id: str
    floods_10y: int
    vulnerabilities: list[str]
    choke_points: list[str]
    events: list[HistoricalEvent] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)  # structural changes since the analogue event
    hazard: str = "flood"


# Feature order used for vector similarity, per hazard
_FEATURES_BY_HAZARD = {
    "flood": ["rain_intensity", "soil_moisture", "headroom_deficit", "drainage_stress"],
    "wildfire": ["fuel_dryness", "aridity_index", "wind_kick", "thermal_anomaly", "ignition_reports"],
    "cyclone": ["storm_wind", "surge_coupling", "rain_burst", "track_pressure"],
    "earthquake": ["ground_accel", "energy_release", "building_vulnerability", "shaking_reports"],
    "tsunami": ["sea_disturbance", "source_energy", "coastal_exposure", "sea_state_report"],
    "volcanic": ["tremor_amplitude", "so2_flux", "ash_plume", "ashfall_report"],
    "landslide": ["slope_saturation", "rain_trigger", "terrain_fragility", "slippage_report"],
    "drought": ["precipitation_deficit", "soil_desiccation", "heat_stress", "water_scarcity"],
    "heatwave": ["thermal_excess", "dry_bulb_load", "stagnation", "heat_illness"],
}

_DRIVER_LABELS_BY_HAZARD = {
    "flood": {
        "rain_intensity": "Rainfall intensity",
        "soil_moisture": "Soil saturation",
        "headroom_deficit": "Drainage headroom",
        "drainage_stress": "Drainage overload",
        "citizen_pressure": "Ground reports",
    },
    "wildfire": {
        "fuel_dryness": "Fuel dryness",
        "aridity_index": "Aridity index",
        "wind_kick": "Wind gusts",
        "thermal_anomaly": "Thermal anomaly",
        "ignition_reports": "Ignition reports",
        "citizen_pressure": "Ground reports",
    },
    "cyclone": {
        "storm_wind": "Wind field",
        "surge_coupling": "Surge coupling",
        "rain_burst": "Rain burst",
        "track_pressure": "Track pressure",
        "citizen_pressure": "Ground reports",
    },
    "earthquake": {
        "ground_accel": "Peak ground accel",
        "energy_release": "Energy release",
        "building_vulnerability": "Building vulnerability",
        "shaking_reports": "Shaking reports",
        "citizen_pressure": "Ground reports",
    },
    "tsunami": {
        "sea_disturbance": "Sea disturbance",
        "source_energy": "Source energy",
        "coastal_exposure": "Coastal exposure",
        "sea_state_report": "Sea-state reports",
        "citizen_pressure": "Ground reports",
    },
    "volcanic": {
        "tremor_amplitude": "Volcanic tremor",
        "so2_flux": "SO2 flux",
        "ash_plume": "Ash plume",
        "ashfall_report": "Ashfall reports",
        "citizen_pressure": "Ground reports",
    },
    "landslide": {
        "slope_saturation": "Slope saturation",
        "rain_trigger": "Rain trigger",
        "terrain_fragility": "Terrain fragility",
        "slippage_report": "Slippage reports",
        "citizen_pressure": "Ground reports",
    },
    "drought": {
        "precipitation_deficit": "Precipitation deficit",
        "soil_desiccation": "Soil desiccation",
        "heat_stress": "Heat stress",
        "water_scarcity": "Water scarcity",
        "citizen_pressure": "Ground reports",
    },
    "heatwave": {
        "thermal_excess": "Thermal excess",
        "dry_bulb_load": "Dry-bulb load",
        "stagnation": "Wind stagnation",
        "heat_illness": "Heat illness",
        "citizen_pressure": "Ground reports",
    },
}


def _features(hazard: str) -> list[str]:
    return _FEATURES_BY_HAZARD.get(hazard, _FEATURES_BY_HAZARD["flood"])


def _driver_labels(hazard: str) -> dict[str, str]:
    return _DRIVER_LABELS_BY_HAZARD.get(hazard, _DRIVER_LABELS_BY_HAZARD["flood"])


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
    # California wildfire theatre — real event names, synthetic signatures
    "ca_santa_rosa": ZoneMemory(
        "ca_santa_rosa", floods_10y=4,
        vulnerabilities=["Dense WUI blocks on ridge flanks", "utility corridors through fuel-dry canyons"],
        choke_points=["Highway 101 ridgeline pass", "Mark West Creek drainage corridor"],
        divergences=[
            "PG&E de-energization protocol active since 2019 — ignition exposure lowered",
            "Fuel-break program cut ~30% of dead-ladder fuel along the western flank",
        ],
        events=[
            HistoricalEvent("Tubbs Fire", "Oct 2017", 5, {"fuel_dryness": 10.5, "aridity_index": 10.0, "wind_kick": 11.0, "thermal_anomaly": 9.5, "ignition_reports": 8.0}, "wind-driven WUI firestorm", hazard="wildfire"),
            HistoricalEvent("Kincade Fire", "Oct 2019", 4, {"fuel_dryness": 9.8, "aridity_index": 9.0, "wind_kick": 9.5, "thermal_anomaly": 8.5, "ignition_reports": 6.0}, "red-flag transmission ignition", hazard="wildfire"),
        ],
        hazard="wildfire",
    ),
    "ca_paradise": ZoneMemory(
        "ca_paradise", floods_10y=5,
        vulnerabilities=["Ridge pine fuel beds", "single-lane evacuation network"],
        choke_points=["Skyway ridge corridor", "Midway culvert crossing"],
        divergences=[
            "Rebuild since 2018 enforces ember-resistant construction and wider defensible space",
            "Evacuation capacity tripled with the new ridge connector",
        ],
        events=[
            HistoricalEvent("Camp Fire", "Nov 2018", 5, {"fuel_dryness": 11.0, "aridity_index": 10.5, "wind_kick": 10.5, "thermal_anomaly": 10.0, "ignition_reports": 9.0}, "ember-storm WUI fire", hazard="wildfire"),
            HistoricalEvent("North Complex", "Aug 2020", 4, {"fuel_dryness": 10.0, "aridity_index": 9.5, "wind_kick": 8.5, "thermal_anomaly": 9.0, "ignition_reports": 7.0}, "lightning-ignited complex", hazard="wildfire"),
        ],
        hazard="wildfire",
    ),
    "ca_mariposa": ZoneMemory(
        "ca_mariposa", floods_10y=6,
        vulnerabilities=["Sierra foothill oak woodland", "remote trailhead access"],
        choke_points=["Highway 140 canyon reach", "Yosemite gateway corridor"],
        divergences=[
            "Prescribed-burn program reduced surface fuel loads ~25% since 2017",
            "Red-flag pre-positioning of crews on the 140 corridor since 2021",
        ],
        events=[
            HistoricalEvent("Detwiler Fire", "Jul 2017", 4, {"fuel_dryness": 10.2, "aridity_index": 9.8, "wind_kick": 8.0, "thermal_anomaly": 9.0, "ignition_reports": 6.5}, "foothill brush fire with canyon wind", hazard="wildfire"),
            HistoricalEvent("Ferguson Fire", "Jul 2018", 4, {"fuel_dryness": 10.0, "aridity_index": 9.5, "wind_kick": 7.5, "thermal_anomaly": 8.8, "ignition_reports": 6.0}, "Yosemite gateway closure event", hazard="wildfire"),
        ],
        hazard="wildfire",
    ),
    "ca_la_basin": ZoneMemory(
        "ca_la_basin", floods_10y=3,
        vulnerabilities=["Interface canyons above residential basins", "aged power distribution on ridge flanks"],
        choke_points=["Interstate 405 canyon crossing", "Mulholland corridor"],
        divergences=[
            "Vegetation-management zones tightened under the 2019 wildfire plan",
            "Weather-triggered public safety power shutoffs now standard",
        ],
        events=[
            HistoricalEvent("Woolsey Fire", "Nov 2018", 4, {"fuel_dryness": 9.5, "aridity_index": 9.0, "wind_kick": 10.5, "thermal_anomaly": 9.0, "ignition_reports": 7.5}, "Santa Ana wind-driven fire", hazard="wildfire"),
            HistoricalEvent("Saddle Ridge Fire", "Oct 2019", 3, {"fuel_dryness": 9.0, "aridity_index": 8.5, "wind_kick": 8.5, "thermal_anomaly": 8.0, "ignition_reports": 5.0}, "foothill fire near the basin rim", hazard="wildfire"),
        ],
        hazard="wildfire",
    ),
    "ca_sd_backcountry": ZoneMemory(
        "ca_sd_backcountry", floods_10y=4,
        vulnerabilities=["Chaparral fuel corridors", "dispersed backcountry settlements"],
        choke_points=["Interstate 8 east pass", "Campo ridge road"],
        divergences=[
            "San Diego County fire code restricts building within 100 ft of fuel corridors",
            "Santa Ana forecast pre-deployment since 2007 improved response times",
        ],
        events=[
            HistoricalEvent("Cedar Fire", "Oct 2003", 5, {"fuel_dryness": 11.0, "aridity_index": 10.5, "wind_kick": 10.0, "thermal_anomaly": 10.5, "ignition_reports": 8.0}, "Santa Ana firestorm", hazard="wildfire"),
            HistoricalEvent("Witch Creek Fire", "Oct 2007", 4, {"fuel_dryness": 10.5, "aridity_index": 9.8, "wind_kick": 9.5, "thermal_anomaly": 9.5, "ignition_reports": 7.0}, "wind-driven chaparral fire", hazard="wildfire"),
        ],
        hazard="wildfire",
    ),
}

# Generic profiles for zones without bespoke memory
_GENERIC_EVENTS = [
    HistoricalEvent("Chennai Floods", "Dec 2015", 5, {"rain_intensity": 10.8, "soil_moisture": 9.4, "headroom_deficit": 10.0, "drainage_stress": 10.5}, "compound cyclonic inundation", hazard="flood"),
    HistoricalEvent("NE monsoon inundation", "Nov 2021", 4, {"rain_intensity": 9.2, "soil_moisture": 8.2, "headroom_deficit": 8.2, "drainage_stress": 8.8}, "monsoon onset saturation", hazard="flood"),
]

_GENERIC_WILDFIRE_EVENTS = [
    HistoricalEvent("Heat-dome brush fire", "Sep 2020", 4, {"fuel_dryness": 10.5, "aridity_index": 9.8, "wind_kick": 9.0, "thermal_anomaly": 9.5, "ignition_reports": 6.5}, "drought-prime ridge fire", hazard="wildfire"),
    HistoricalEvent("Red-flag wind event", "Oct 2022", 3, {"fuel_dryness": 9.0, "aridity_index": 8.8, "wind_kick": 8.5, "thermal_anomaly": 8.0, "ignition_reports": 4.5}, "offshore wind with dry fuels", hazard="wildfire"),
]

_GENERIC_VULN = ["stormwater network at design limit", "low-lying street flooding"]
_GENERIC_CHOKE = ["primary drain outfall", "river-adjacent culvert"]
_GENERIC_DIVERGENCES = [
    "Reservoir pre-discharge protocols lowered base basin levels ~1.2 m vs 2015",
    "Stormwater network upgraded in patches since 2015 — coverage is uneven",
]
_GENERIC_WILDFIRE_VULN = ["fuel-dry vegetation in interface zones", "limited road egress on ridge lines"]
_GENERIC_WILDFIRE_CHOKE = ["ridge evacuation corridor", "canyon wind funnel"]
_GENERIC_WILDFIRE_DIVERGENCES = [
    "Utility de-energization protocols active since 2019 — ignition exposure lowered",
    "Fuel-break programs uneven across districts — coverage is partial",
]

_GENERIC_CYCLONE_EVENTS = [
    HistoricalEvent("Bay of Bengal cyclone", "Oct 2019", 4, {"storm_wind": 10.0, "surge_coupling": 9.0, "rain_burst": 8.5, "track_pressure": 8.0}, "landfall with surge band", hazard="cyclone"),
    HistoricalEvent("Coastal depression track", "Nov 2021", 3, {"storm_wind": 8.5, "surge_coupling": 7.5, "rain_burst": 7.0, "track_pressure": 6.5}, "moderate coastal impact", hazard="cyclone"),
]
_GENERIC_CYCLONE_VULN = ["surge-range coastal blocks", "dense fishing-community wards"]
_GENERIC_CYCLONE_CHOKE = ["coastal road corridor", "harbour access line"]
_GENERIC_CYCLONE_DIVERGENCES = [
    "Cyclone shelters upgraded to multi-hazard standards since 2020",
    "Early-warning dissemination via mobile broadcast now standard",
]

# Seismic / geologic / climate hazards — generic event bands for non-bespoke zones
_GENERIC_SEISMIC_EVENTS = {
    "earthquake": [
        HistoricalEvent("Seismic episode sequence", "2016", 4, {"ground_accel": 9.5, "energy_release": 10.0, "building_vulnerability": 7.0, "shaking_reports": 7.5}, "mainshock with active aftershocks", hazard="earthquake"),
        HistoricalEvent("Moderate ground-motion event", "2019", 3, {"ground_accel": 7.0, "energy_release": 7.5, "building_vulnerability": 6.5, "shaking_reports": 5.0}, "damaging shaking with limited sequence", hazard="earthquake"),
    ],
    "tsunami": [
        HistoricalEvent("Offshore-source surge", "2011", 5, {"sea_disturbance": 11.0, "source_energy": 10.5, "coastal_exposure": 8.5, "sea_state_report": 8.0}, "far-field surge event", hazard="tsunami"),
        HistoricalEvent("Local sea-floor event", "2018", 3, {"sea_disturbance": 8.0, "source_energy": 7.5, "coastal_exposure": 8.0, "sea_state_report": 5.5}, "near-field disturbance", hazard="tsunami"),
    ],
    "volcanic": [
        HistoricalEvent("Explosive eruption cycle", "2014", 4, {"tremor_amplitude": 10.0, "so2_flux": 9.5, "ash_plume": 9.0, "ashfall_report": 7.5}, "tremor and flux escalation", hazard="volcanic"),
        HistoricalEvent("Ashfall episode", "2017", 3, {"tremor_amplitude": 7.5, "so2_flux": 7.0, "ash_plume": 7.5, "ashfall_report": 6.5}, "moderate plume with ashfall", hazard="volcanic"),
    ],
    "landslide": [
        HistoricalEvent("Monsoon slope failure", "2013", 4, {"slope_saturation": 10.5, "rain_trigger": 10.0, "terrain_fragility": 8.0, "slippage_report": 7.0}, "burst-triggered runout", hazard="landslide"),
        HistoricalEvent("Saturation creep event", "2019", 3, {"slope_saturation": 8.5, "rain_trigger": 7.5, "terrain_fragility": 7.5, "slippage_report": 5.5}, "slow mobilization on wet face", hazard="landslide"),
    ],
    "drought": [
        HistoricalEvent("Multi-season drought", "2016", 4, {"precipitation_deficit": 10.5, "soil_desiccation": 10.0, "heat_stress": 8.5, "water_scarcity": 8.0}, "compounding deficit years", hazard="drought"),
        HistoricalEvent("Monsoon-break drought", "2019", 3, {"precipitation_deficit": 8.5, "soil_desiccation": 8.0, "heat_stress": 7.0, "water_scarcity": 6.0}, "failed monsoon onset", hazard="drought"),
    ],
    "heatwave": [
        HistoricalEvent("Heat-dome episode", "2016", 4, {"thermal_excess": 10.5, "dry_bulb_load": 9.5, "stagnation": 9.0, "heat_illness": 7.5}, "stagnant dome with high night floor", hazard="heatwave"),
        HistoricalEvent("Hot-corridor event", "2019", 3, {"thermal_excess": 8.5, "dry_bulb_load": 8.0, "stagnation": 7.0, "heat_illness": 5.5}, "multi-day corridor heat", hazard="heatwave"),
    ],
}
_GENERIC_GEOLOGIC_VULN = ["pre-2010 building stock", "critical lifelines crossing hazard corridors"]
_GENERIC_GEOLOGIC_CHOKE = ["bridge and culvert crossings", "hill corridor junctions"]
_GENERIC_GEOLOGIC_DIVERGENCES = [
    "Building codes tightened after the last major event — coverage is uneven",
    "Early-warning dissemination via mobile broadcast now standard",
]


def memory_for(zone_id: str, hazard: str = "flood") -> ZoneMemory:
    mem = _MEMORY.get(zone_id)
    if mem and mem.hazard == hazard:
        return mem
    if hazard == "wildfire":
        return ZoneMemory(zone_id, floods_10y=4, vulnerabilities=list(_GENERIC_WILDFIRE_VULN),
                          choke_points=list(_GENERIC_WILDFIRE_CHOKE), events=list(_GENERIC_WILDFIRE_EVENTS),
                          divergences=list(_GENERIC_WILDFIRE_DIVERGENCES), hazard="wildfire")
    if hazard == "cyclone":
        return ZoneMemory(zone_id, floods_10y=4, vulnerabilities=list(_GENERIC_CYCLONE_VULN),
                          choke_points=list(_GENERIC_CYCLONE_CHOKE), events=list(_GENERIC_CYCLONE_EVENTS),
                          divergences=list(_GENERIC_CYCLONE_DIVERGENCES), hazard="cyclone")
    if hazard in _GENERIC_SEISMIC_EVENTS:
        return ZoneMemory(zone_id, floods_10y=4, vulnerabilities=list(_GENERIC_GEOLOGIC_VULN),
                          choke_points=list(_GENERIC_GEOLOGIC_CHOKE), events=list(_GENERIC_SEISMIC_EVENTS[hazard]),
                          divergences=list(_GENERIC_GEOLOGIC_DIVERGENCES), hazard=hazard)
    return ZoneMemory(zone_id, floods_10y=3, vulnerabilities=list(_GENERIC_VULN),
                      choke_points=list(_GENERIC_CHOKE), events=list(_GENERIC_EVENTS),
                      divergences=list(_GENERIC_DIVERGENCES))


def _vec(comps: dict[str, float], hazard: str) -> list[float]:
    return [comps.get(f, 0.0) for f in _features(hazard)]


def _similarity(a: list[float], b: list[float]) -> float:
    """Inverse normalized euclidean → 0..1 (1 = identical signature)."""
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return float(max(0.0, min(1.0, 1.0 - d / 14.0)))


def analogue_matches(zone_id: str, components: dict[str, float], hazard: str = "flood") -> list[dict]:
    """Top historical analogues for the current feature state (hazard-scoped)."""
    mem = memory_for(zone_id, hazard)
    vec = _vec(components, hazard)
    scored = [
        {"event": e.name, "date": e.date, "severity": e.severity,
         "similarity": round(_similarity(vec, _vec(e.signature, hazard)), 3),
         "description": e.description}
        for e in mem.events if e.hazard == hazard
    ]
    return sorted(scored, key=lambda s: -s["similarity"])


def _matching_drivers(components: dict[str, float], signature: dict[str, float],
                      hazard: str = "flood") -> list[dict]:
    """Which causal drivers line up with the analogue event (within 70% of its signature)."""
    labels = _driver_labels(hazard)
    out = []
    for k in _features(hazard):
        cur = components.get(k, 0.0)
        ref = signature.get(k, 0.0)
        ratio = cur / ref if ref > 0 else 0.0
        out.append({
            "driver": labels.get(k, k),
            "feature": k,
            "current": round(cur, 2),
            "analogue": ref,
            "matched": ratio >= 0.7,
        })
    return out


def _reliability(components: dict[str, float], signature: dict[str, float],
                 similarity: float, divergences: list[str], hazard: str = "flood") -> str:
    """Analogue reliability: pattern overlap minus structural drift."""
    matched = sum(1 for d in _matching_drivers(components, signature, hazard) if d["matched"])
    base = similarity
    # structural drift discounts reliability
    drift_penalty = min(0.25, 0.08 * len(divergences))
    score = base - drift_penalty + 0.06 * matched
    if score >= 0.75:
        return "High"
    if score >= 0.5:
        return "Moderate"
    return "Low"


def memory_view(zone_id: str, components: dict[str, float], hazard: str = "flood") -> dict:
    mem = memory_for(zone_id, hazard)
    matches = analogue_matches(zone_id, components, hazard)
    top = matches[0] if matches else None
    top_event = next((e for e in mem.events if top and e.name == top["event"] and e.date == top["date"]), None)
    drivers = _matching_drivers(components, top_event.signature, hazard) if top_event else []
    reliability = _reliability(components, top_event.signature, top["similarity"], mem.divergences, hazard) if top_event else "Low"
    decade_label = {"wildfire": "wildfire seasons", "cyclone": "cyclone landfalls"}.get(
        hazard,
        {
            "earthquake": "seismic episodes",
            "tsunami": "tsunami events",
            "volcanic": "eruption cycles",
            "landslide": "slope failures",
            "drought": "drought episodes",
            "heatwave": "heat-dome episodes",
        }.get(hazard, "inundation events"),
    )
    return {
        "zone_id": zone_id,
        "hazard": hazard,
        "historical_floods_10y": mem.floods_10y,
        "known_vulnerabilities": mem.vulnerabilities,
        "choke_points": mem.choke_points,
        "top_analogues": matches,
        "headline": (
            f"{mem.floods_10y} major {decade_label} in the past decade; current telemetry "
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
