# 04 — Multi-Agent Architecture

Each agent implements a common contract:

```python
class Agent(Protocol):
    mission: str
    def run(self, ctx: AgentContext) -> AgentResult: ...
```

`AgentResult` = `{outputs, confidence, messages[], used_sources[], failure: None|reason}`.
Handoff protocol: outputs are typed dataclasses validated by the receiving agent;
on failure, orchestrator logs a `handoff_failed` event and continues with degraded inputs.

| Agent | Mission | Inputs → Outputs |
|---|---|---|
| Satellite | Soil moisture / SAR wetness anomaly | GPM-like frames → wetness index |
| Weather | Rainfall nowcast + forecast | rain gauge/forecast series → hourly rain forecast |
| Air Quality | AQ anomalies (context for haze/heat) | AQ stream → anomaly flag |
| Water | River/canal level + drainage headroom | water level series, capacity → headroom %, breach risk |
| Citizen Report | Crowdsourced ground truth | reports (text+geocode) → verified incident clusters |
| News | Event mentions, official warnings | news items → event tags, credibility |
| Risk Fusion | Fuse agent outputs into risk state | all above → per-location risk components |
| Prediction | Forecast risk probability/severity/horizon | fused state → forecast + bounds |
| Explanation | Build causal chain + attribution | fused state + forecast → causal nodes, attributions |
| Recommendation | Operational checklists by stakeholder | risk + forecast → prioritized actions |
| Simulation | What-if intervention impact | intervention + state → before/after deltas |

## Debate engine

When `confidence < 0.55`, `DebateEngine` launches two agent roles (e.g., `Water` vs
`Weather`) that each produce a structured case over shared evidence; the verdict
(note: LLM optional) is generated from the contrast. Always rendered with both
positions and the evidence each cites.
