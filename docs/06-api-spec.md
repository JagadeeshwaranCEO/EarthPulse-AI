# 06 — API Specification

Base: `/api/v1` · OpenAPI at `/docs` (Swagger) and `/openapi.json`.

## REST

| Method | Path | Purpose |
|---|---|---|
| GET | `/dashboard` | Pulse score, active alerts, top risks, crisis flag |
| GET | `/locations` | All monitored locations |
| GET | `/risks` | Risk summaries (risk level, confidence, trend, horizon) |
| GET | `/risks/{id}` | Full detail: components, causal chain, evidence, attribution |
| GET | `/risks/{id}/prediction?horizon=24` | Forecast series + uncertainty bands |
| GET | `/risks/{id}/recommendations` | Stakeholder checklists + priorities |
| GET | `/risks/{id}/causal-chain` | Node graph: cause → mechanism → risk |
| GET | `/risks/{id}/attribution` | Feature influence (permutation) |
| GET | `/risks/{id}/evidence` | Provenance ledger |
| POST | `/simulations` | Run what-if (intervention + params) → before/after |
| GET | `/simulations/{id}` | Simulation result incl. carbon ledger |
| GET | `/agents` | Agent roster (mission, status, confidence) |
| POST | `/agents/{name}/run` | Run one agent's pipeline |
| GET | `/agents/debate?topic=&risk_id=` | AI debate view (confidence-gated) |
| POST | `/chat` | Copilot chat (LLM or template fallback) |
| GET | `/pulse?location_id=` | Pulse score + factor breakdown |

## WebSocket

`/ws` — live tick: `{type: "tick", time, pulse, alerts[], top_risks[]}` pushed every
`TICK_SECONDS` from the background simulator. Frontend subscribes once, mission
control stays live.

## Error contract

`{"error": {"code": str, "message": str, "trace_id": str}}` · 404/422/503 semantics.
Every AI response includes `"llm_mode": "live" | "fallback"`.
