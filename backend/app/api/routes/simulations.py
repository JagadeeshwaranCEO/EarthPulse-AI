"""Simulations — run what-if interventions, persist runs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.core.db import get_db
from app.core.models import Location, SimulationRun
from app.schemas import SimulationRequest, SimulationResult
from app.services.simulation_engine import available_interventions, run_simulation

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("/interventions")
def list_interventions():
    return available_interventions()


@router.post("", response_model=SimulationResult)
def create_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    loc = db.get(Location, req.location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    outputs, _ = build_agent_outputs(db, req.location_id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    result = run_simulation(components, loc.population, req.interventions)
    result["location_id"] = req.location_id
    db.add(SimulationRun(
        id=result["id"], location_id=req.location_id, event_type=req.event_type,
        params={"interventions": req.interventions}, result=result,
    ))
    db.commit()
    return result


@router.get("/{sim_id}")
def get_simulation(sim_id: str, db: Session = Depends(get_db)):
    run = db.get(SimulationRun, sim_id)
    if run is None:
        raise HTTPException(404, "simulation not found")
    return run.result
