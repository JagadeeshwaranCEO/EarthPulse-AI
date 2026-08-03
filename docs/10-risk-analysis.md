# 10 — Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Keyless demo (no LLM key) | High | Medium | Deterministic template fallback everywhere; `llm_mode` surfaced in UI |
| Python 3.14 dep wheels | Medium | High | Minimal deps; numpy/scikit only; uv lockfile pins |
| Overbuild vs hackathon deadline | High | High | 13-day slices; every feature must serve the demo story |
| Map breaks in demo (network tiles) | Low | High | Leaflet with bundled CARTO tiles fallback + offline circle render |
| WebSocket flakiness | Low | Medium | REST refresh fallback on ws error |
| Judges doubt data | Medium | High | Every seed row is `is_synthetic` + provenance-tagged; story says "pilot with public data hooks" |
| Prediction model underpowered | Medium | Medium | Honest uncertainty bands; framing = early warning, not actuarial accuracy |

## Failure modes (agent contract)

Every agent declares `failure_mode`; orchestrator logs `handoff_failed` and continues
degraded. Missing sensor → fused risk shows widened uncertainty, not a crash.
