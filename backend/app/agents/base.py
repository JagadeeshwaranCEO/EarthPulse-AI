"""Agent contract — every agent declares mission, inputs, outputs, memory,
confidence, handoff protocol, and failure mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    location_id: str
    event_type: str = "flood"
    payload: dict[str, Any] = field(default_factory=dict)
    run_id: str = ""


@dataclass
class AgentResult:
    outputs: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    messages: list[str] = field(default_factory=list)
    used_sources: list[str] = field(default_factory=list)
    failure: str | None = None


class BaseAgent:
    name: str = "base"
    mission: str = ""
    inputs: list[str] = []
    outputs: list[str] = []
    failure_mode: str = ""

    def run(self, ctx: AgentContext) -> AgentResult:  # pragma: no cover
        raise NotImplementedError
