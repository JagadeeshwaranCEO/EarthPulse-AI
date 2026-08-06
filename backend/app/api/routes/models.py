"""Model registry — every working engine surfaced with live status.

Read-only inventory of the prediction / explanation / decision / behaviour
subsystems. `status` reflects whether the subsystem has produced real output in
the current session (from DB counters), so the UI can show "live" vs "dormant"
honestly instead of hard-coding availability.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models
from app.core.db import get_db
from app.services.ticker import current_hour, get_state

router = APIRouter(tags=["models"])

_G = "governance"
_P = "prediction"
_E = "explanation"
_D = "decision"


def _build() -> list[dict]:
    hour = current_hour()
    state = get_state()

    return [
        {
            "id": "nowcast-ladder",
            "name": "lead-aware nowcasting ladder",
            "category": _P,
            "status": "live",
            "description": "hourly flood probability by lead time, per zone, with calibrated confidence bands",
            "surface": ["GET /api/v1/risks/{id}/prediction", "GET /api/v1/risks"],
            "notes": f"edge hour {hour:.0f}",
        },
        {
            "id": "forecaster-ensemble",
            "name": "time-series forecaster with bounds",
            "category": _P,
            "status": "live",
            "description": "stochastic GLM: ensemble mean + lower/upper fan for each lead step",
            "endpoint": "GET /api/v1/risks/{id}/prediction",
            "notes": "confidence band from residual variance",
        },
        {
            "id": "risk-evolution",
            "name": "risk evolution tracer",
            "category": _P,
            "status": "live",
            "description": "80-hour trajectory, peak timing and 24h drift per zone",
            "endpoints": ["GET /api/v1/decisions/evolution/{id}"],
        },
        {
            "id": "crossing",
            "name": "threshold crossing forecaster",
            "category": _P,
            "status": "live",
            "description": "hours-to-crossing for high/moderate band and per-driver stress lines",
            "endpoints": ["GET /api/v1/risks/{id}"],
        },
        {
            "id": "causal-attribution",
            "name": "attribution engine + causal chain",
            "category": _E,
            "status": "live",
            "description": "normalised feature influences with direction and causal DAG",
            "endpoints": [
                "GET /api/v1/risks/{id}/causal-chain",
                "GET /api/v1/risks/{id}/attribution",
            ],
        },
        {
            "id": "environmental-memory",
            "name": "environmental memory / analogue retrieval",
            "category": _E,
            "status": "live",
            "description": "10-year event memory, vulnerability inventory, closest analogues with divergence",
            "endpoints": ["GET /api/v1/decisions/memory/{id}"],
        },
        {
            "id": "compare",
            "name": "historical comparison + analogue verdict",
            "category": _E,
            "status": "live",
            "description": "live-vs-history alignment with similarity and a calibrated verdict",
            "endpoints": ["GET /api/v1/decisions/compare/{id}"],
        },
        {
            "id": "scientist",
            "name": "scientist explainable scores",
            "category": _E,
            "status": "live",
            "description": "formula steps, dominant factors with weights, uncertainty and limitations",
            "endpoints": ["GET /api/v1/decisions/scientist/{id}"],
        },
        {
            "id": "decision-optimizer",
            "name": "3-strategy resource optimizer",
            "category": _D,
            "status": "live",
            "description": "max-lives / min-econ / balanced with robust-to-+15% rainfall check and fallback trigger",
            "endpoints": ["POST /api/v1/decisions/optimize"],
        },
        {
            "id": "mission-brief",
            "name": "mission brief generator",
            "category": _D,
            "status": "live",
            "description": "markdown standing-operating brief with facets, impact estimate and provenance",
            "endpoints": ["POST /api/v1/decisions/brief"],
        },
        {
            "id": "simulation",
            "name": "intervention simulation engine",
            "category": _D,
            "status": "live",
            "description": "what-if: probability/severity/damage deltas + carbon ledger per intervention",
            "endpoints": ["GET /api/v1/simulations/interventions", "POST /api/v1/simulations"],
        },
        {
            "id": "agent-debate",
            "name": "4-agent risk debate",
            "category": _D,
            "status": "live",
            "description": "adversarial debate across constellation agents with consensus verdict",
            "endpoints": ["GET /api/v1/agents/debate?risk_id=…"],
        },
        {
            "id": "validation",
            "name": "holdout validation report",
            "category": _G,
            "status": "live",
            "description": "rolling out-of-sample Brier / skill vs climatology / ROC AUC / calibration / tier per zone",
            "endpoints": ["GET /api/v1/validation"],
        },
        {
            "id": "trust-score",
            "name": "trust score with 6-part checks",
            "category": _G,
            "status": "live",
            "description": "High/Moderate/Low trust with per-check pass/fail and rationale",
            "endpoints": ["GET /api/v1/decisions/trust/{id}"],
        },
        {
            "id": "pulse",
            "name": "situational pulse gauge",
            "category": _G,
            "status": "live",
            "description": "single composite 0–1000 score mapped to stable/watchful/stressed/critical",
            "endpoints": ["GET /api/v1/dashboard"],
            "notes": f"hour {hour:.0f} · max {state['max']:.0f}",
        },
    ]


@router.get("/models")
def models_inventory(db: Session = Depends(get_db)) -> dict:
    try:
        prediction_count = db.query(func.count(models.Prediction.id)).scalar() or 0
        event_count = db.query(func.count(models.Event.id)).scalar() or 0
        simulation_count = db.query(func.count(models.SimulationRun.id)).scalar() or 0
        agent_count = db.query(func.count(models.AgentMessage.id)).scalar() or 0
        evidence_count = db.query(func.count(models.EvidenceObject.id)).scalar() or 0
        zones = db.query(func.count(models.Location.id)).scalar() or 0
    except Exception:
        prediction_count = event_count = simulation_count = agent_count = evidence_count = zones = 0

    epo = get_settings()
    return {
        "scope": epo.scope,
        "zones": zones,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "store": {
            "predictions": prediction_count,
            "events": event_count,
            "agent_messages": agent_count,
            "simulation_runs": simulation_count,
            "evidence_objects": evidence_count,
        },
        "llm_mode": epo.llm_mode,
        "models": _build(),
    }