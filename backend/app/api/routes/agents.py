"""Agents: roster, single-agent runs, debate view, audit trail."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agents.debate import DEBATE_THRESHOLD, debate
from app.agents.orchestrator import PIPELINE, ROSTER, run_pipeline
from app.agents.base import AgentContext
from app.core.db import get_db
from app.core.models import AgentMessage, Location, Prediction

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
def get_roster(db: Session = Depends(get_db)):
    roster = []
    for name, agent in ROSTER.items():
        last = (
            db.query(AgentMessage)
            .filter_by(agent=name)
            .order_by(desc(AgentMessage.created_at))
            .first()
        )
        roster.append({
            "name": name,
            "mission": agent.mission,
            "status": "failed" if last and last.failure else "ready",
            "confidence": round(last.confidence, 2) if last else 0.0,
            "last_output": last.content if last else "",
            "inputs": agent.inputs,
            "outputs": agent.outputs,
            "failure_mode": agent.failure_mode,
        })
    return roster


@router.get("/pipeline")
def get_pipeline(db: Session = Depends(get_db)):
    return [
        db.query(AgentMessage)
        .filter_by(agent=name)
        .order_by(desc(AgentMessage.created_at))
        .first()
        .content if db.query(AgentMessage).filter_by(agent=name).count() else "pending"
        for name in PIPELINE
    ]


@router.post("/{name}/run")
def run_agent(name: str, location_id: str, db: Session = Depends(get_db)):
    if name not in ROSTER:
        raise HTTPException(404, "unknown agent")
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(404, "location not found")
    return run_pipeline(db, location_id)


@router.get("/debate")
async def get_debate(topic: str = "Chennai monsoon flood risk", risk_id: str = "", force: bool = False, db: Session = Depends(get_db)):
    pred = None
    if risk_id:
        pred = (
            db.query(Prediction)
            .filter_by(location_id=risk_id, event_type="flood")
            .order_by(desc(Prediction.generated_at))
            .first()
        )
    if not force and pred and pred.confidence >= DEBATE_THRESHOLD:
        return {
            "topic": topic, "risk_id": risk_id, "statements": [],
            "verdict": f"Confidence {pred.confidence:.0%} is above the debate threshold "
                       f"({DEBATE_THRESHOLD:.0%}); agents agree. No debate invoked.",
            "llm_mode": "n/a",
        }
    components = pred.features if pred else {}
    evidence = [e.description for e in ([] if pred is None else [])]
    return await debate(components, [], topic, risk_id)
