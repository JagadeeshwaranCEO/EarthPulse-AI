# EarthPulse AI — API Specification

*Document 3/6. Covers deliverable 10. Base URL: `/api/v1`. All responses are JSON; errors use RFC 7807 problem+json. Live updates over `/ws/live`.*

---

## 1. Conventions

- Auth (V1): optional `X-API-Key` header; demo mode is open read-only.
- Pagination: `?limit=&offset=`; list responses wrap in `{ items: [], total, next }`.
- Every risk-bearing response includes `evidence_ids` and `model_id` (provenance contract).
- Timestamps: ISO 8601 UTC.

## 2. Endpoints

### 2.1 Health & meta

```
GET /health                      → { status, version, model_versions[], sources_healthy{} }
GET /regions                     → list of regions + wards (GeoJSON)
```

### 2.2 Risk

```
GET /risk/summary?region=chennai&horizon_h=48
  → { as_of, wards: [ { ward_id, name, geometry, probability, severity, pulse, updated_at } ] }

GET /risk/{ward_id}?horizon_h=24|48|72
  → {
      ward_id, event_id, probability, severity,
      confidence: { lo, hi, method, calibration_bins },
      time_horizon_h, model_id,
      feature_attribution: [ { feature, shap, direction } ],
      evidence: [ { evidence_id, source, kind, weight, description } ],
      limitations: [ "..." ],
      pulse_impact: { score_before, score_after_delta }
    }

GET /risk/timeseries?ward_id=&metric=probability|stage|rainfall&hours=168
  → { points: [ { ts, value, lo, hi } ] }
```

### 2.3 Causal & explanation

```
GET /causal/{event_id}
  → { nodes: [ { id, type: 'rain|soil|stage|flow|saturation|flood', value, status } ],
      edges: [ { from, to, strength, direction } ],
      root_causes: [ "..." ] }

GET /explain/{risk_id}?format=markdown
  → { narrative, citations: [ { evidence_id, quote, url } ],
      shap_top_features: [...], uncertainty_reasons: [...], model_notes }

POST /debate
  { topic_id: risk_id }
  → { rounds: [ { agent: 'hydrologist'|'statistician', claim, evidence_ids[], confidence, rebuttals[] } ],
      verdict: { agreed, disagreed_on[], moderator_note } }
```

### 2.4 Simulation

```
POST /simulate
  { event_id, intervention: { kind: 'pumps'|'sandbags'|'evacuation'|'retrofit', params: {...} } }
  → {
      baseline: { flooded_ha, affected_population, damage_usd, co2e_t },
      after:    { ... },
      delta:    { flooded_ha, affected_population, damage_usd, co2e_t, pct },
      confidence_bounds, method, model_id,
      timeline: [ { h, stage_m, flooded_ha, with_intervention_flooded_ha } ]
    }

GET /simulations/{run_id}     → archived run (audit)
```

### 2.5 Recommendations

```
GET /recommendations/{risk_id}
  → { priority, checklist: [ { step, owner, urgency, deadline_h } ],
      stakeholder_briefs: { public, ops, commissioner },
      interventions: [ { kind, expected_reduction_pct, cost, est_time_h } ],
      rationale: [ evidence_ids ] }

GET /alerts?level=WARNING&active=true   → active alerts
POST /alerts/{id}/dispatch              → dispatch via channels (demo: no-op, logged)
```

### 2.6 Planet Pulse & ledger

```
GET /pulse?region=chennai
  → { score, grade, components: { flood, wildfire, air, water, heat }, weights, delta_24h, rationale }

GET /pulse/history?region=&days=30      → score series for the time-scrubber

GET /ledger?region=&window=30d
  → { interventions_run, estimated_damage_prevented_usd,
      estimated_co2e_avoided_t, methodology, citations }
```

### 2.7 Inputs

```
POST /reports/citizen
  { lat, lng, type: 'flooding'|'dumping'|'water_quality'|'air', photos[], notes }
  → { report_id, cluster_id, weight, acknowledgment }

GET /sources/status                    → per-source staleness + health (transparency)
```

### 2.8 Copilot

```
POST /copilot/chat
  { messages: [...], context: { ward_id?, event_id?, session_id } }
  → { reply, grounded_in: [ evidence_ids ], tool_calls: [ { tool, args } ] }
```

### 2.9 Live telemetry (WebSocket)

```
WS /ws/live?region=chennai
  server → { type: 'tick', as_of } | { type: 'risk_update', ward_id, probability, severity }
         | { type: 'alert', alert } | { type: 'crisis_state', on: bool, reason }
         | { type: 'source_health', source, status }
```

## 3. Error contract

```json
{ "type": "https://earthpulse.dev/errors/stale_source",
  "title": "Stale source", "status": 503,
  "detail": "River gauge CWC-ADYAR last updated 6h ago.",
  "instance": "/risk/CHENNAI-W142" }
```

## 4. Implementation notes

- FastAPI routers mirror the section layout (`routers/risk.py`, `routers/simulation.py`, ...).
- All read paths hit Postgres directly; heavy compute (simulation, debate, explanation) runs as background tasks with `job_id` + `GET /jobs/{id}` polling.
- WebSocket broadcasts via an in-process pub/sub hub (single node in demo).

---

*Next: docs/04-ui-plan.md*
