"""Pydantic API contracts — mirror the entities but shape for the UI."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_id: str
    source_name: str
    kind: str
    url: str | None = None
    is_synthetic: bool = True


class Evidence(BaseModel):
    id: str
    kind: str
    captured_at: datetime
    description: str
    value: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class AttributionItem(BaseModel):
    feature: str
    influence: float
    direction: str  # raises | lowers risk
    description: str = ""


class CausalNode(BaseModel):
    id: str
    label: str
    kind: str  # cause | mechanism | condition | risk
    value: str = ""
    confidence: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)


class CausalEdge(BaseModel):
    source: str
    target: str
    label: str = ""


class CausalChain(BaseModel):
    nodes: list[CausalNode]
    edges: list[CausalEdge]


class RiskSummary(BaseModel):
    location_id: str
    location_name: str
    lat: float
    lon: float
    event_type: str
    level: str  # low | moderate | high | critical
    risk_probability: float
    severity: float
    confidence: float
    trend: str  # rising | steady | falling
    horizon_h: int
    updated_at: datetime


class RiskDetail(RiskSummary):
    components: dict[str, float] = Field(default_factory=dict)
    attribution: list[AttributionItem] = Field(default_factory=list)
    causal_chain: CausalChain = Field(default_factory=lambda: CausalChain(nodes=[], edges=[]))
    evidence: list[Evidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    model_name: str = ""
    llm_mode: str = "fallback"


class ForecastPoint(BaseModel):
    t: datetime
    mean: float
    lower: float
    upper: float


class Recommendation(BaseModel):
    id: str
    stakeholder: str  # civic | responders | public | utilities
    priority: int
    action: str
    reasoning: str
    evidence_ids: list[str] = Field(default_factory=list)


class DebateStatement(BaseModel):
    agent: str
    position: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class DebateResult(BaseModel):
    topic: str
    risk_id: str = ""
    statements: list[DebateStatement]
    verdict: str = ""
    llm_mode: str = "fallback"


class SimulationRequest(BaseModel):
    location_id: str
    event_type: str = "flood"
    interventions: dict[str, float] = Field(default_factory=dict)  # id -> intensity 0..1
    horizon_h: int = 48


class SimulationResult(BaseModel):
    id: str
    location_id: str
    baseline: dict[str, Any]
    after: dict[str, Any]
    deltas: dict[str, Any]
    carbon_ledger: dict[str, Any]
    llm_mode: str = "fallback"


class ChatMessage(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    location_id: str = ""


class ChatResponse(BaseModel):
    reply: str
    llm_mode: str = "fallback"
    trace: list[str] = Field(default_factory=list)


class PulseView(BaseModel):
    location_id: str
    score: float
    factors: dict[str, float]
    recorded_at: datetime
    band: str  # stable | watchful | stressed | critical


class Dashboard(BaseModel):
    pulse: PulseView
    alerts: list[dict[str, Any]]
    risks: list[RiskSummary]
    crisis: bool
    time: datetime
    tick_seconds: float


class AgentRoster(BaseModel):
    name: str
    mission: str
    status: str
    confidence: float
    last_output: str = ""
