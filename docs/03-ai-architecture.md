# 03 — AI Architecture

## Model assignments (per blueprint: never LLM for raw prediction)

| Job | Model | Why appropriate |
|---|---|---|
| Risk prediction | Streaming exponential smoothing + residual-uncertainty bands | Deterministic, explainable, real-time; upgrade path to Prophet/satellite-ml |
| Anomaly detection | IsolationForest over normalized sensor stream | Multivariate, robust to distribution shift, fast |
| Explanation | LLM (keyless fallback templates) + permutation attribution + evidence ledger | LLM only narrates; attribution is numeric |
| Action planning | Rule-guided planner + optional LLM reasoning | Prioritized, auditable checklists |
| Simulation | Water-balance/hazard algebra engine (numpy) | Instant what-if, physically interpretable |
| Debate | Two LLM roles over shared evidence | Confidence-gated; fallback to evidence contrast |

## Confidence & uncertainty

- `confidence ∈ [0,1]` per prediction = agreement among agents weighted by source freshness.
- `uncertainty_bounds` = quantile bands from residual distribution of the forecaster.
- Every score carries `data_sources[]`, `limitations[]`, and an `evidence[]` trail.

## LLM governance

- `LLM_MODE`: `auto` (key present → live, else fallback) / `templates` (forced offline).
- Fallback outputs are deterministic, evidence-grounded templates — never hallucinated.
