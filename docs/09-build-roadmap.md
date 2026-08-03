# 09 — Build Roadmap (13 days)

| Day | Deliverable | Exit criteria |
|---|---|---|
| 1 | Design contract (docs 01–08) + repo scaffold | Backend boots, frontend boots |
| 2 | Data models + Chennai seed + ingestion | `/locations` returns 15 zones with provenance |
| 3 | Forecaster + anomaly + attribution | `/risks/{id}/prediction` shows bands |
| 4 | 11 agents + orchestrator | `/agents` roster; pipeline run → messages |
| 5 | Risk fusion + pulse score | `/dashboard` coherent |
| 6 | REST API complete + tests | smoke tests green |
| 7 | Frontend skeleton: layout, map, left rail | Map renders zones with colors |
| 8 | Risk detail + causal chain + attribution panes | Click zone → full story |
| 9 | Simulation sandbox + before/after + carbon ledger | What-if changes risk visibly |
| 10 | Debate engine + copilot + evidence panels | Low-confidence risks show debate |
| 11 | Crisis mode + WebSocket live tick + time scrubber | Demo stays live with WS |
| 12 | Hardening: keyless fallback, error contract, README, docker | `docker compose up` runs all |
| 13 | Demo rehearsal: script, story beats, fallback plan | 5-min story told end-to-end |

## Slice order (always shippable)

1. Boot both apps (blank slate) — day 1
2. Static seed → live API — day 2–3
3. Risk story end-to-end (map → detail → causal → sim) — day 7–9
4. Multi-agent theatre + live tick — day 10–11
5. Crisis polish — day 12–13
