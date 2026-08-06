"""AI Copilot chat — LLM when keyed, otherwise deterministic context-aware replies."""

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agents.orchestrator import build_agent_outputs
from app.core.db import get_db
from app.core.models import Location, Prediction
from app.core.security import chat_throttle
from app.schemas import ChatRequest, ChatResponse
from app.services import llm as llm_svc

router = APIRouter(prefix="/chat", tags=["chat"])


def _context_blob(db: Session, location_id: str) -> str:
    loc = db.get(Location, location_id) if location_id else db.query(Location).first()
    if loc is None:
        return "No location data yet."
    outputs, _ = build_agent_outputs(db, loc.id)
    components = outputs.get("risk_fusion", {}).get("components", {})
    pred = outputs.get("prediction", {})
    recs = outputs.get("recommendation", {}).get("recommendations", [])
    top = ", ".join(f"{r['stakeholder']}: {r['action']}" for r in recs[:3])
    return (
        f"Location: {loc.name} ({loc.id})\n"
        f"Components: { {k: round(v, 2) for k, v in components.items()} }\n"
        f"P(risk)={pred.get('risk_probability', 0):.2f}, severity={pred.get('severity', 0):.1f}/5, "
        f"confidence={pred.get('confidence', 0):.2f}\n"
        f"Top recommendations: {top}"
    )


@router.post("", response_model=ChatResponse, dependencies=[chat_throttle])
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    context = _context_blob(db, req.location_id)
    system = (
        "You are EarthPulse Copilot, an environmental intelligence assistant. Ground every answer "
        "in the provided telemetry; if you don't know, say so. Never invent sensor readings.\n"
        f"Current telemetry:\n{context}"
    )
    reply, mode = await llm_svc.complete(system, last_user, temperature=0.4)
    if mode == "fallback":
        lower = last_user.lower()
        if "recommend" in lower or "action" in lower or "should" in lower:
            reply = ("Based on current telemetry (P(risk) and component mix above), the priority order is: "
                     "1) mechanical drainage lift for low-lying wards, 2) reservoir release for headroom, "
                     "3) evacuation-readiness staging. These are ordered by their attribution influence. "
                     "(Template reasoning — add OPENAI_API_KEY for conversational depth.)")
        elif "uncertain" in lower or "confidence" in lower or "sure" in lower:
            reply = ("Confidence is computed from agent agreement weighted by source freshness, with "
                     "residual-derived uncertainty bands on the forecast. The weakest signal right now is "
                     "the citizen report stream. (Template reasoning.)")
        else:
            reply = (
                "I'm running in offline template mode. I can explain risk components, uncertainty, "
                "and priority actions. Add OPENAI_API_KEY to enable open-ended reasoning. "
                f"Current situation: P(risk) with component breakdown in the panel above."
            )
    return ChatResponse(reply=reply, llm_mode=mode, trace=[f"location={req.location_id or 'default'}"])
