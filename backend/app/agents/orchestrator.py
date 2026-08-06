"""Agent registry + orchestrator.

Runs the flood pipeline: sensors → observers → fusion → prediction → explanation
→ recommendation. Logs every step as an AgentMessage (audit trail) and applies the
handoff protocol: on failure, mark handoff_failed and continue degraded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agents.base import AgentContext, AgentResult
from app.agents.cognition import (
    ExplanationAgent,
    PredictionAgent,
    RecommendationAgent,
    RiskFusionAgent,
    SimulationAgent,
)
from app.agents.observers import CitizenReportAgent, NewsAgent
from app.agents.sensors import AirQualityAgent, SatelliteAgent, WaterAgent, WeatherAgent
from app.core import models
from app.services.ticker import current_hour, get_anchor

ALL_AGENTS: list = [
    SatelliteAgent(),
    WeatherAgent(),
    AirQualityAgent(),
    WaterAgent(),
    CitizenReportAgent(),
    NewsAgent(),
    RiskFusionAgent(),
    PredictionAgent(),
    ExplanationAgent(),
    RecommendationAgent(),
    SimulationAgent(),
]

ROSTER = {a.name: a for a in ALL_AGENTS}

PIPELINE = [
    "satellite",
    "weather",
    "air_quality",
    "water",
    "citizen_report",
    "news",
    "risk_fusion",
    "prediction",
    "explanation",
    "recommendation",
]


def _load_payload(db: Session, location: models.Location) -> dict:
    hour = current_hour()
    n_weather = min(72, max(3, int(hour)))
    n_sat = min(36, max(1, int(hour // 2)))

    weather_rows = (
        db.query(models.WeatherSnapshot)
        .filter_by(location_id=location.id)
        .order_by(models.WeatherSnapshot.captured_at)
        .all()
    )
    sat_rows = (
        db.query(models.SatelliteFrame)
        .filter_by(location_id=location.id)
        .order_by(models.SatelliteFrame.captured_at)
        .all()
    )

    # Truncate to the sim clock; beyond the seed window, extrapolate a decaying
    # storm tail (marked extrapolated so provenance stays honest).
    weather = [
        {
            "rainfall_mm": w.rainfall_mm,
            "rain_forecast_mm": w.rain_forecast_mm,
            "humidity": w.humidity,
            "wind_kmh": w.wind_kmh,
            "source_id": w.source_id,
        }
        for w in weather_rows[:n_weather]
    ]
    if hour > 72 and weather:
        last = weather[-1]
        for k in range(1, min(int(hour) - 72, 8) + 1):
            decay = 0.86**k
            weather.append(
                {
                    "rainfall_mm": last["rainfall_mm"] * decay,
                    "rain_forecast_mm": last["rain_forecast_mm"] * decay,
                    "humidity": max(55.0, last["humidity"] * (1.0 - 0.02 * k)),
                    "wind_kmh": last.get("wind_kmh", 0),
                    "source_id": f"imd-rain:extrapolated:h{72 + k}",
                }
            )
    sat = [
        {
            "soil_moisture_anomaly": f.soil_moisture_anomaly,
            "surface_water_index": f.surface_water_index,
            "source_id": f.source_id,
        }
        for f in sat_rows[:n_sat]
    ]
    if hour > 72 and sat:
        last = sat[-1]
        for k in range(1, min(int(hour) // 2 - 36, 4) + 1):
            sat.append(
                {
                    "soil_moisture_anomaly": max(0.0, last["soil_moisture_anomaly"] * 0.94**k),
                    "surface_water_index": max(0.0, last["surface_water_index"] * 0.93**k),
                    "source_id": "gpm-nasa:extrapolated",
                }
            )

    n_reports = max(0, int(hour))
    reports = [
        {"verified": c.verified, "source_id": c.source_id}
        for c in db.query(models.CitizenReport).filter_by(location_id=location.id).all()
        if _report_hour(c.reported_at) <= n_reports
    ]

    seismic = [
        {
            "metric": d.metric,
            "value": d.value,
            "unit": d.unit,
            "source_id": d.source_id,
            "captured_at": d.captured_at.isoformat(),
            "is_synthetic": d.is_synthetic,
        }
        for d in db.query(models.IngestedDatum)
        .filter_by(location_id=location.id)
        .order_by(models.IngestedDatum.captured_at)
        .all()
    ]

    return {
        "location_id": location.id,
        "event_type": location.hazard_type,
        "hazard_type": location.hazard_type,
        "population": location.population,
        "drainage_capacity_mmh": location.drainage_capacity_mmh,
        "exposure": (location.attributes or {}).get("exposure", 1.0),
        "sim_hour": hour,
        "satellite_frames": sat,
        "weather_snapshots": weather,
        "seismic": seismic,
        "water_level_series": [
            {"level_m": 0.0, "capacity_m": 1.0, "inflow_m3s": 0.0, "source_id": "n/a", "source_ok": True}
        ],
        "citizen_reports": reports,
        "news_items": [],
        "aq_stream": [],
        "now": datetime.now(timezone.utc),
        "horizon_h": 24,
    }


def _report_hour(ts) -> int:
    """Approximate seed-relative hour from an ISO timestamp (seed anchors at -72h)."""
    try:
        anchor = get_anchor()
        if not anchor:
            return 0  # unknown anchor → include report (do not silently drop)
        base = datetime.fromisoformat(anchor)
        dt = datetime.fromisoformat(str(ts))
        delta = (dt - base).total_seconds() / 3600.0
        return int(delta)
    except Exception:
        logging.getLogger("earthpulse.agents").warning(
            "report-hour mapping failed for %s — treating as t0", ts, exc_info=True
        )
        return 0


def build_agent_outputs(db: Session, location_id: str, extras: dict | None = None) -> tuple[dict, AgentResult]:
    """Run sensing+fusion+prediction+explanation for a location. Returns (outputs, fused_result)."""
    location = db.query(models.Location).get(location_id)
    if location is None:
        raise KeyError(location_id)

    from app.hazards.registry import get_hazard

    hazard = get_hazard(location.hazard_type)
    payload = _load_payload(db, location)
    if hazard.id == "flood":
        water_levels = payload["water_level_series"]
        if water_levels:
            snaps = payload["weather_snapshots"]
            exposure = payload.get("exposure", 1.0)
            cap = payload.get("drainage_capacity_mmh", 8.0)
            sum6 = sum(s["rainfall_mm"] for s in snaps[-6:])
            deficit = min(12.0, sum6 / 26.0 * exposure)
            stress = min(12.0, max(0.0, (sum6 / max(1.0, cap) - 8.0) / 3.0 * exposure))
            level = min(1.0, 0.2 + sum6 / 156.0 * exposure)
            water_levels[0] = {
                "level_m": round(level, 3),
                "capacity_m": 1.0,
                "inflow_m3s": round(min(60.0, 8 + sum6 * 0.9), 1),
                "headroom_deficit": round(deficit, 2),
                "drainage_stress": round(stress, 2),
                "source_id": "seed:cwprs-ccb",
                "source_ok": True,
            }
        payload["water_level_series"] = water_levels

    payload["historical_features"] = hazard.history(payload)
    if extras:
        payload.update(extras)

    ctx = AgentContext(location_id=location_id, run_id=f"run_{uuid4().hex[:8]}", payload=payload)

    outputs: dict[str, dict] = {}
    for name in PIPELINE:
        agent = ROSTER[name]
        result = agent.run(ctx)
        record = result.outputs
        if result.confidence is not None:
            record["_conf"] = result.confidence
        outputs[name] = record
        if result.failure:
            outputs[name]["_failure"] = result.failure
        ctx.payload["agent_outputs"] = outputs
        ctx.payload["prediction"] = outputs.get("prediction") or {}
        ctx.payload["components"] = outputs.get("risk_fusion", {}).get("components") or {}

    fused = outputs.get("risk_fusion", {})
    fused_result = AgentResult(outputs=fused, confidence=fused.get("components_confidence", 0.5))
    return outputs, fused_result


def run_pipeline(db: Session, location_id: str, persist: bool = True) -> dict:
    """Full pipeline run with audit trail persistence."""
    outputs, _ = build_agent_outputs(db, location_id)
    run_id = f"run_{uuid4().hex[:10]}"
    if persist:
        for name, record in outputs.items():
            db.add(
                models.AgentMessage(
                    run_id=run_id,
                    agent=name,
                    content=record.get("_msg") or f"agent produced {len(record)} fields",
                    confidence=record.get("_conf", 0.0),
                    used_sources=[],
                    failure=record.get("_failure"),
                )
            )
        db.commit()
    return {"run_id": run_id, "outputs": outputs}


def roster(db: Session) -> list[dict]:
    return [
        {"name": a.name, "mission": a.mission, "status": "ready", "confidence": 0.0, "last_output": ""}
        for a in ALL_AGENTS
    ]
