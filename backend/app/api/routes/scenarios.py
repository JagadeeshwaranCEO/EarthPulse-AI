"""Scenario simulator API — launch + replay digital-twin hazard sweeps."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models
from app.core.db import get_db
from app.core.ops import publish
from app.core.security import require_api_key
from app.services.scenario import ScenarioParams, broadcast_peak_alerts, run_scenario, scenario_to_dict

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

PRESETS = [
    {
        "id": "bay-of-bengal-cyclone",
        "name": "Bay of Bengal Cyclone — landfall drill",
        "hazard_type": "cyclone",
        "start_lat": 14.1, "start_lon": 81.2,
        "end_lat": 10.9, "end_lon": 78.3,
        "intensity": 0.92, "radius_km": 150, "duration_h": 14,
    },
    {
        "id": "eastern-ghats-slide",
        "name": "Eastern Ghats Landslide wave",
        "hazard_type": "landslide",
        "start_lat": 12.9, "start_lon": 79.6,
        "end_lat": 10.2, "end_lon": 78.1,
        "intensity": 0.85, "radius_km": 70, "duration_h": 10,
    },
    {
        "id": "andhra-flood",
        "name": "Andhra riverine flood surge",
        "hazard_type": "flood",
        "start_lat": 16.5, "start_lon": 80.5,
        "end_lat": 12.4, "end_lon": 79.7,
        "intensity": 0.90, "radius_km": 110, "duration_h": 16,
    },
    {
        "id": "deccan-heatwave",
        "name": "Deccan Plateau heatwave",
        "hazard_type": "heatwave",
        "start_lat": 15.7, "start_lon": 78.9,
        "end_lat": 11.2, "end_lon": 77.6,
        "intensity": 0.88, "radius_km": 180, "duration_h": 24,
    },
    {
        "id": "western-ghats-tsunami",
        "name": "West Coast tsunami run",
        "hazard_type": "tsunami",
        "start_lat": 13.2, "start_lon": 80.0,
        "end_lat": 10.4, "end_lon": 76.9,
        "intensity": 0.80, "radius_km": 60, "duration_h": 6,
    },
]


class ScenarioBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    hazard_type: str = "cyclone"
    start_lat: float = Field(ge=-90, le=90)
    start_lon: float = Field(ge=-180, le=180)
    end_lat: float = Field(ge=-90, le=90)
    end_lon: float = Field(ge=-180, le=180)
    intensity: float = Field(default=0.9, ge=0.1, le=1.0)
    radius_km: float = Field(default=130, ge=10, le=600)
    duration_h: int = Field(default=12, ge=1, le=72)
    step_h: int = Field(default=1, ge=1, le=6)
    zoom_h: int = Field(default=1, ge=0, le=8)
    broadcast: bool = False


def _frames(db: Session, run_id: str) -> list[dict]:
    steps = db.scalars(
        select(models.ScenarioStep).where(models.ScenarioStep.run_id == run_id).order_by(models.ScenarioStep.t_index.asc())
    ).all()
    return [s.frame for s in steps]


@router.get("/presets")
def presets():
    return PRESETS


@router.get("")
def list_scenarios(limit: int = Query(default=20, le=100), db: Session = Depends(get_db)):
    runs = db.scalars(select(models.ScenarioRun).order_by(models.ScenarioRun.created_at.desc()).limit(limit)).all()
    return [scenario_to_dict(r, []) for r in runs]


@router.post("", dependencies=[require_api_key])
def create_scenario(body: ScenarioBody, db: Session = Depends(get_db)):
    frames = body.duration_h // body.step_h + 1
    if frames > get_settings().scenario_max_steps:
        raise HTTPException(422, f"run too long — max {get_settings().scenario_max_steps} frames")
    params = ScenarioParams(
        name=body.name,
        hazard_type=body.hazard_type,
        start_lat=body.start_lat,
        start_lon=body.start_lon,
        end_lat=body.end_lat,
        end_lon=body.end_lon,
        intensity=body.intensity,
        radius_km=body.radius_km,
        duration_h=body.duration_h,
        step_h=body.step_h,
        zoom_h=body.zoom_h,
    )
    scenario = run_scenario(db, params)
    if body.broadcast:
        broadcast_peak_alerts(db, scenario, level="critical")
    try:
        publish(
            {
                "type": "scenario",
                "action": "created",
                "scenario_id": scenario.id,
                "name": scenario.name,
                "impact": scenario.summary.get("impact_score"),
                "zones": scenario.summary.get("affected_zones"),
            }
        )
    except Exception:
        pass
    return scenario_to_dict(scenario, [])


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db)):
    scenario = db.get(models.ScenarioRun, scenario_id)
    if scenario is None:
        raise HTTPException(404, "scenario not found")
    return scenario_to_dict(scenario, _frames(db, scenario_id))


@router.post("/{scenario_id}/broadcast", dependencies=[require_api_key])
def broadcast_drill(scenario_id: str, db: Session = Depends(get_db)):
    scenario = db.get(models.ScenarioRun, scenario_id)
    if scenario is None:
        raise HTTPException(404, "scenario not found")
    raised = broadcast_peak_alerts(db, scenario, level="critical")
    return {"scenario_id": scenario_id, "alerts_raised": raised}


@router.delete("/{scenario_id}", dependencies=[require_api_key])
def delete_scenario(scenario_id: str, db: Session = Depends(get_db)):
    scenario = db.get(models.ScenarioRun, scenario_id)
    if scenario is None:
        raise HTTPException(404, "scenario not found")
    db.query(models.ScenarioStep).filter(models.ScenarioStep.run_id == scenario_id).delete()
    db.delete(scenario)
    db.commit()
    return {"deleted": scenario_id}