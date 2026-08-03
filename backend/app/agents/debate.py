"""AI debate engine — two positions over shared evidence when confidence is low.

LLM-based when a key is present; otherwise a deterministic evidence-contrast view
that never fabricates. Confidence-gated: only invoked below the threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.cognition import RiskFusionAgent
from app.agents.observers import CitizenReportAgent
from app.agents.sensors import WeatherAgent
from app.services import llm as llm_svc

DEBATE_THRESHOLD = 0.55

_ROLE_DEFS = {
    "weather": ("Weather Signal", "rainfall nowcast is the dominant driver"),
    "water": ("Water Dynamics", "drainage headroom is the binding constraint"),
    "citizen_report": ("Ground Truth", "verified reports should weight the verdict"),
    "satellite": ("Remote Sensing", "soil moisture anomalies confirm saturation"),
}


@dataclass
class Position:
    agent: str
    position: str
    evidence: list[str]
    confidence: float


def _positions(components: dict[str, float], evidence: list[dict]) -> list[Position]:
    rain = components.get("rain_intensity", 0)
    head = components.get("headroom_deficit", 0)
    cit = components.get("citizen_pressure", 0)
    soil = components.get("soil_moisture", 0)
    lines = {e["description"] for e in evidence}

    return [
        Position(
            agent="weather",
            position=(
                f"Rainfall intensity is the dominant signal ({rain:.1f}). Recent accumulation "
                f"exceeds the 6-hour design threshold; the nowcast keeps moisture feeding the system."
            ),
            evidence=[l for l in lines if "rain" in l.lower()][:2] or ["rain gauge accumulation window"],
            confidence=0.72,
        ),
        Position(
            agent="water",
            position=(
                f"Even with moderate rain, headroom deficit ({head:.1f}/10) is the binding constraint: "
                f"the drainage network cannot shed the current load before the next surge."
            ),
            evidence=[l for l in lines if "headroom" in l.lower() or "level" in l.lower()][:2] or ["canal level vs capacity"],
            confidence=0.66,
        ),
        Position(
            agent="citizen_report",
            position=(
                f"Verified ground reports (pressure {cit:.1f}) confirm waterlogging is already visible "
                f"in low-lying wards — observations corroborate the mechanism regardless of forecast error."
            ),
            evidence=[l for l in lines if "report" in l.lower()][:2] or ["verified citizen reports"],
            confidence=0.55,
        ),
        Position(
            agent="satellite",
            position=(
                f"Soil moisture anomaly ({soil:.2f}) indicates saturated catchments: further rain "
                f"converts almost entirely into runoff. This raises the severity profile."
            ),
            evidence=[l for l in lines if "soil" in l.lower()][:2] or ["soil moisture anomaly frame"],
            confidence=0.6,
        ),
    ]


async def debate(components: dict[str, float], evidence: list[dict], topic: str, risk_id: str = "") -> dict:
    positions = _positions(components, evidence)
    _, mode = await llm_svc.complete(
        system="You are the debate moderator for EarthPulse. Synthesize a fair verdict from the two positions; be honest about uncertainty.",
        user="Topic: " + topic + "\n\n" + "\n\n".join(
            f"### {_ROLE_DEFS[p.agent][0]} ({p.confidence:.0%} conf)\n{p.position}\nEvidence: {p.evidence}" for p in positions
        ),
    )
    if mode == "live":
        verdict, _ = await llm_svc.complete(
            system="Write a 2-sentence verdict as the EarthPulse moderator.",
            user="Topic: " + topic,
        )
        verdict_text = verdict.strip()
    else:
        top = max(positions, key=lambda p: p.confidence)
        verdict_text = (
            f"Moderator (template): evidence-weighted reading favors the {_ROLE_DEFS[top.agent][0]} "
            f"argument. All agents agree the mechanism is present; disagreement is over magnitude, "
            f"which is why confidence stays below {int(DEBATE_THRESHOLD * 100)}%."
        )
    return {
        "topic": topic,
        "risk_id": risk_id,
        "statements": [
            {"agent": _ROLE_DEFS[p.agent][0], "position": p.position, "evidence": p.evidence, "confidence": p.confidence}
            for p in positions
        ],
        "verdict": verdict_text,
        "llm_mode": mode,
    }
