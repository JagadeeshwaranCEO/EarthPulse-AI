"""Scenario simulator — a deterministic "digital twin" of a hazard marching
across the whole theatre.

A hazard (cyclone/flood/wildfire/...) sweeps on a linear track with a Gaussian
intensity field that deepens with time. Every zone answers with an
hour-by-hour risk probability + alert level derived from the hazard's own
thresholds, and the sweep is frozen into frames the UI can animate. The whole
run is explainable: probability falls off ∝ exp(-(d/R)²) and is nudged by the
zone's own exposure terrain (elevation, drainage for fluvial hazards).

No randomness, no network — deterministic and instant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core import models
from app.hazards.registry import get_hazard

EARTH_R = 6371.0


@dataclass
class ScenarioParams:
    name: str
    hazard_type: str = "cyclone"
    start_lat: float = 13.5
    start_lon: float = 79.6
    end_lat: float = 11.5
    end_lon: float = 78.2
    intensity: float = 0.9  # 0-1 storm strength
    radius_km: float = 130.0
    duration_h: int = 12
    step_h: int = 1
    zoom_h: int = 1  # UI sprint factor (0 = native)
    broadcast: bool = False  # raise critical alerts + allow SMS/Ghost at peak


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def _theatre_span(zones: list[models.Location]) -> float:
    """Bounding diagonal (km) of the theatre — drives storm sizing."""
    if not zones:
        return 400.0
    lats = [z.lat for z in zones]
    lons = [z.lon for z in zones]
    return max(
        haversine_km(min(lats), min(lons), max(lats), max(lons)),
        haversine_km(min(lats), max(lons), max(lats), min(lons)),
    )


def _effective_radius(p: ScenarioParams, zones: list[models.Location]) -> float:
    """A storm that matters for the whole theatre: user radius, but never
    smaller than ~2/5 of the theatre span (hazard-scaled for slow hazards)."""
    scale = {"drought": 2.6, "heatwave": 2.1, "earthquake": 1.4}.get(p.hazard_type, 1.0)
    return max(p.radius_km * scale, _theatre_span(zones) * 0.40)


def _storm_center(p: ScenarioParams, t: int, eff_r: float) -> tuple[float, float, float]:
    """Storm position + effective radius at hour t (track lerp, deepening core)."""
    f = (t / p.duration_h) if p.duration_h else 0.0
    lat = p.start_lat + (p.end_lat - p.start_lat) * f
    lon = p.start_lon + (p.end_lon - p.start_lon) * f
    r = eff_r * (1.0 + 0.22 * math.sin(math.pi * f))
    return lat, lon, r


def _zone_risk(p: ScenarioParams, loc: models.Location, t: int, eff_r: float) -> float:
    """Gaussian sweep scaled by terrain exposure → probability 0..1."""
    lat, lon, r = _storm_center(p, t, eff_r)
    d = haversine_km(loc.lat, loc.lon, lat, lon)
    core = p.intensity * math.exp(-((d / r) ** 2))

    exposure = float(loc.attributes.get("exposure", 0.7)) if loc.attributes else 0.7
    if p.hazard_type in ("flood", "cyclone", "tsunami"):
        terrain = (1.0 - max(0.0, min(1.0, loc.elevation_m / 40.0))) * 0.35
        drainage = (1.0 - max(0.0, min(1.0, loc.drainage_capacity_mmh / 14.0))) * 0.25
        exposure = max(0.0, min(1.0, exposure * (1.0 + terrain + drainage - 0.2)))
    elif p.hazard_type in ("landslide", "wildfire"):
        exposure = max(0.0, min(1.0, exposure * (1.0 + min(1.0, loc.elevation_m / 80.0) * 0.4)))

    reach = {"drought": 0.55, "heatwave": 0.65, "earthquake": 0.8}.get(p.hazard_type, 1.0)
    return round(min(0.97, max(0.0, core * exposure * reach)), 3)


def propagate(zones: list[models.Location], p: ScenarioParams) -> dict:
    """March the hazard through `zones`; returns {frames, summary}."""
    hazard = get_hazard(p.hazard_type)
    eff_r = _effective_radius(p, zones)
    frames: list[dict] = []
    wake: dict[str, dict] = {}

    for t in range(0, p.duration_h + 1, p.step_h):
        snap: list[dict] = []
        for loc in zones:
            prob = _zone_risk(p, loc, t, eff_r)
            level = hazard.level(prob)
            snap.append({"id": loc.id, "name": loc.name, "lat": loc.lat, "lon": loc.lon, "p": prob, "level": level})
            w = wake.setdefault(loc.id, {"id": loc.id, "name": loc.name, "pop": loc.population, "peak_p": 0.0, "peak_t": t, "first_c": None})
            if prob >= 0.30 and w["first_c"] is None:
                w["first_c"] = t
        frames.append({"t": t, "zones": snap, "crisis": sum(1 for z in snap if z["level"] == "critical")})

    for snap in frames:
        for z in snap["zones"]:
            w = wake[z["id"]]
            if z["p"] > w["peak_p"]:
                w["peak_p"] = z["p"]
                w["peak_t"] = snap["t"]

    for w in wake.values():
        w["peak_level"] = hazard.level(w["peak_p"])

    wake_list = sorted(wake.values(), key=lambda w: w["peak_p"], reverse=True)
    affected = [w for w in wake_list if w["peak_p"] >= 0.3]
    critical = [w for w in wake_list if w["peak_level"] == "critical"]
    peak_pop = sum(w["pop"] * w["peak_p"] for w in affected)
    impact_score = round(100.0 * sum(w["peak_p"] for w in wake_list) / max(1, len(wake_list)), 1)

    worst = max(wake_list, key=lambda w: (w["peak_p"], w["pop"])) if wake_list else None
    evac_lead_min = 0
    if worst and worst["first_c"] is not None and worst["peak_t"] > worst["first_c"]:
        evac_lead_min = (worst["peak_t"] - worst["first_c"]) * 60

    shelter_cap = int(round(sum(w["pop"] * w["peak_p"] * 0.12 for w in critical)))
    first_crisis = next((f["t"] for f in frames if f["crisis"] > 0), None)

    return {
        "frames": frames,
        "summary": {
            "hazard": hazard.label,
            "frames": len(frames),
            "affected_zones": len(affected),
            "critical_peak_zones": len(critical),
            "affected_population": int(round(peak_pop)),
            "impact_score": impact_score,
            "shelter_capacity_recommended": shelter_cap,
            "evacuation_lead_minutes": evac_lead_min,
            "first_crisis_h": first_crisis,
            "peak_crisis_h": max(frames, key=lambda f: f["crisis"])["t"] if frames else 0,
            "top_zones": [
                {
                    "id": w["id"],
                    "name": w["name"],
                    "peak_p": w["peak_p"],
                    "peak_t": w["peak_t"],
                    "peak_level": w["peak_level"],
                    "population": w["pop"],
                    "shelter_recommended": int(round(w["pop"] * w["peak_p"] * 0.12)),
                }
                for w in wake_list[:6]
            ],
        },
    }


def run_scenario(db: Session, p: ScenarioParams) -> models.ScenarioRun:
    """Persist a scenario run + its frames. Deterministic."""
    zones = list(db.query(models.Location).order_by(models.Location.id.asc()).all())
    result = propagate(zones, p)

    run = models.ScenarioRun(
        id=f"scn_{uuid4().hex[:10]}",
        name=p.name,
        hazard_type=p.hazard_type,
        start_lat=p.start_lat,
        start_lon=p.start_lon,
        end_lat=p.end_lat,
        end_lon=p.end_lon,
        intensity=p.intensity,
        radius_km=p.radius_km,
        duration_h=p.duration_h,
        step_h=p.step_h,
        zoom_h=p.zoom_h,
        status="done",
        params={"track": {"start": [p.start_lat, p.start_lon], "end": [p.end_lat, p.end_lon]}},
        summary=result["summary"],
    )
    db.add(run)
    db.flush()
    for frame in result["frames"]:
        db.add(models.ScenarioStep(run_id=run.id, t_index=frame["t"], frame=frame))
    db.commit()
    db.refresh(run)
    return run


def broadcast_peak_alerts(db: Session, run: models.ScenarioRun, level: str = "critical") -> int:
    """Raise real Alert rows for zones at (or above) the given peak level.

    Returns the number of alerts raised. These flow into the normal SMS/Ghost
    pipeline exactly like live alerts — a drill that exercises the whole chain.
    """
    from app.notification.listener import scan_new_alerts

    peak_zone_ids = [z["id"] for z in run.summary.get("top_zones", []) if z["peak_level"] == level]
    raised = 0
    for zid in peak_zone_ids:
        loc = db.get(models.Location, zid)
        if loc is None:
            continue
        existing = db.query(models.Alert).filter_by(location_id=zid, resolved=False).count()
        if existing > 0:
            continue
        peak = next((z for z in run.summary.get("top_zones", []) if z["id"] == zid), {})
        db.add(
            models.Alert(
                location_id=zid,
                event_type=run.hazard_type,
                level=level,
                title=f"[DRILL] {run.name} — {loc.name} at {level} peak",
                summary=f"Scenario '{run.name}': peak risk {peak.get('peak_p', 0):.0%} at hour {peak.get('peak_t', '?')}, "
                f"shelter recommended {peak.get('shelter_recommended', 0)}.",
            )
        )
        raised += 1
    db.commit()
    if raised and _sms_allowed():
        scan_new_alerts(db)
    return raised


def _sms_allowed() -> bool:
    from app.config import get_settings

    return get_settings().sms_enabled


def scenario_to_dict(run: models.ScenarioRun, frames: list[dict] | list[models.ScenarioStep] | None = None) -> dict:
    if frames is None:
        frames = []
    elif frames and hasattr(frames[0], "frame"):
        frames = [s.frame for s in frames]
    return {
        "id": run.id,
        "name": run.name,
        "hazard_type": run.hazard_type,
        "start": [run.start_lat, run.start_lon],
        "end": [run.end_lat, run.end_lon],
        "intensity": run.intensity,
        "radius_km": run.radius_km,
        "duration_h": run.duration_h,
        "step_h": run.step_h,
        "zoom_h": run.zoom_h,
        "status": run.status,
        "summary": run.summary,
        "frames": frames,
        "created_at": run.created_at.isoformat(),
    }
