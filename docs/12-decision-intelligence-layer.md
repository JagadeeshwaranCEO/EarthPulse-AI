# 12 · Decision Intelligence Layer

The Decision Intelligence Layer closes the loop: prediction → explanation → **optimal action**. It converts the Mission Control dashboard from a *monitoring* tool into an *operations* tool — the "Action Intelligence" pinnacle of EarthPulse.

## What got built

### 1 · EarthPulse Decision Optimizer + Decision Confidence
`backend/app/services/decision_optimizer.py`

A deterministic, multi-objective constrained allocator — no LLM, no hardcoded plans.

- **Input**: live risk state (`live_risk_summaries`), population per zone, and a constrained municipal inventory (boats / pumps / shelters / budget ₹cr).
- **Method**: iterative greedy knapsack over (zone, unit) pairs, scored by marginal lives-equivalent impact per rupee, with **per-zone staging caps** (a river front can't stack 20 boats) so the plan stays operationally sane.
- **Capability model**: `CAP_BOAT=1200` people/boat, `CAP_SHELTER=1500`, pump = 0.35×boat throughput; economic exposure = `population × P(risk) × ₹8,500 exposure × (1 − pump/shelter coverage)`; carbon ledger per unit with route-optimized factor.
- **Three Pareto strategies**:
  - **Alpha · Maximal Life Safety** — boats/shelters to densest, highest-probability basins.
  - **Beta · Infrastructure Shield** — pumps to highest-expected-damage corridors (lowest residual loss).
  - **Gamma · Balanced Pareto** (recommended) — normalized multi-objective frontier.
- Verified demo behavior: calm → differentiated staging plans; crisis (hour 66) → Alpha concentrates boats on the top-2 zones while Beta spreads pumps across 6, and all strategies saturate toward total mobilization.
- **Decision Confidence (sensitivity analysis)**: after computing the Pareto set, the optimizer re-runs under a `{0.85–1.60}×` precipitation variance sweep and reports (a) `decision_confidence` — probability the recommended plan stays optimal; (b) `robustness_rainfall_pct` — the variance window; (c) the **fallback strategy** + trigger if the storm overperforms. Verified arc: calm → robust +25%, fallback Beta; crisis → robust +5%, fallback Alpha — the plan honestly degrades as telemetry escalates.
- **Trade-off matrix**: each strategy carries an explicit objective + operational trade-off (Alpha = max population shielded, high burn rate, abandons tier-2 infrastructure; Beta = min economic/structural decay, thin spread; Gamma = Pareto equilibrium) so the optimizer is never a black box.

### 2. Environmental Memory
`backend/app/services/environmental_memory.py`

Per-zone historical store (floods over 10 years, known vulnerabilities, drainage choke points) plus an **analogue matcher**: normalised inverse-euclidean similarity of the *current live telemetry vector* against stored event signatures (2015 Chennai Floods, 2021/2023 monsoon events). Returns e.g. *"resembles Chennai Floods 2015 at 78%"*. All historical data provenance-tagged synthetic.

**Analogue divergence** — the analogue is never applied blindly: `memory_view` also returns (a) per-driver matching (✓ Rainfall intensity / Soil saturation / Drainage overload — matched within 70% of the event signature), (b) **critical divergences** where today structurally differs from the analogue (e.g., "urban permeability −14% since 2015 — runoff response is faster", "reservoir pre-discharge lowered base levels 1.2 m"), and (c) an estimated **reliability** (High/Moderate/Low) that discounts similarity by structural drift.

### 3. Risk Evolution
`backend/app/services/risk_evolution.py`

Replays the pipeline's feature math per simulated hour across the seed window (48h lookback → 24h horizon), producing an honest hour-by-hour risk curve with peak, peak-hour, now-probability and 24h delta — exactly consistent with the live dashboard value at the current clock hour.

### 4. AI Mission Brief
`backend/app/services/mission_brief.py` + `POST /api/v1/decisions/brief`

Stakeholder-readable brief composed from: situation (§ top risks), decision (**_decision confidence_**, robustness window, fallback advisory), trade-off matrix (§ why the plans differ), memory (§ analogue headline), recommended allocations (§ unit dispatch), expected impact (§ lives, ₹ residual loss, carbon) and actions list. Exported as Markdown; **robustness survives the demo** by degrading honestly as telemetry escalates.

### 5. Explain Like a Scientist
`GET /api/v1/decisions/scientist/{location_id}`

Full XAI decomposition of a single score: the weighted component sum (with the exact weights), the logistic squash equation, the calibration mapping, the influence-ranked dominant factors, uncertainty bounds, causal chain and limitations. This is what an honest ML engineer shows before a review board — nothing hidden.

### 6. Operator Timeline (The "When")
`backend/app/services/decision_optimizer.py` → `build_execution_timeline(peak_hour)`

A plan without a schedule is a wish. The recommended strategy now carries an `execution_timeline`: Monitor (T−48h) → Pre-stage (T−36h) → Mobilize (T−24h) → Lockdown (T−12h) → Impact (T−0h), times rendered as `H{peak−k}` so the stepper tracks the live clock. Rendered as a vertical stepper in the Decide tab and as **§7 · Execution timeline** in the exported Mission Brief.

Verified: labels `T-48h…T-0h`, no `[object]/NaN` leakage, zero-inventory runs still emit a graceful "Stand by" plan.

### 7. Trust Score (Data Provenance)
`backend/app/services/trust_score.py` + `GET /api/v1/decisions/trust/{location_id}`

Separates **mathematical confidence** from **operational trust** — because sensors break and satellites get blocked by clouds, and commanders must know whether they're flying blind. Six deterministic checks derived from the live DB state (drainage coverage, satellite freshness vs the sim window, temporal integrity, analogue availability, model stability, sensor outage ratio), weighted → `score/100` → `High ≥ 80 · Moderate ≥ 55 · Low`. UI shows a pulsing glassmorphism **data trust** pill in the RiskDetail header with a click-to-expand decomposition.

Verified: at h60 → **High 100** (satellite 2h old, analogue 79%); at h79 past the seed window → **Moderate 65** (satellite 9h old, analogue 47%) — trust degrades honestly as telemetry ages.

## API surface (adds to previous spec)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/decisions/optimize` | run constrained allocator → 3 strategies + allocations + decision-confidence analysis |
| GET | `/api/v1/decisions/memory/{location_id}` | environmental memory + analogue divergence |
| GET | `/api/v1/decisions/evolution/{location_id}` | hour-by-hour risk curve |
| POST | `/api/v1/decisions/brief` | stakeholder mission brief (markdown + facets incl. decision confidence, trust, timeline) |
| GET | `/api/v1/decisions/scientist/{location_id}` | full formula-level XAI |
| GET | `/api/v1/decisions/trust/{location_id}` | operational data trust decomposition |

## UI additions

- **Decision tab**: Resource Planner (inventory inputs → run → Pareto strategy cards with lives/residual-loss/carbon tiles, action lines, apply-plan state), a **Decision Confidence** block (prediction vs decision confidence, rainfall robustness window, fallback-strategy advisory), the **trade-off matrix**, the **Operator Timeline stepper**, and the Mission Brief composer with `.md` export.
- **Detail tab**: pulsing **data trust** pill (High/Moderate/Low) with click-to-expand provenance decomposition.
- **Memory tab**: Historical record, analogue matches with similarity bars, **analogue divergence** (per-driver ✓ matches vs diverging drivers, critical divergences where the city changed, reliability badge), vulnerability/choke-point columns, hour-by-hour Risk Evolution chart, and the **operator ⇄ explain-like-a-scientist** mode toggle revealing the full formula trace.
- Tab bar made scrollable in `Panel.tsx` (`Tabs`).

## Files

```
backend/app/services/decision_optimizer.py
backend/app/services/environmental_memory.py
backend/app/services/risk_evolution.py
backend/app/services/mission_brief.py
backend/app/services/trust_score.py
backend/app/api/routes/decision.py
backend/tests/test_smoke.py            (12 tests incl. decision API + strategy-differ + trust asserts)
frontend/components/panels/DecisionPanel.tsx
frontend/components/panels/MemoryPanel.tsx
frontend/components/ui/TrustPill.tsx
frontend/components/viz/EvolutionChart.tsx
frontend/lib/api.ts
```

3. **Positioning**: this layer is what moves EarthPulse from "AI dashboard" to a
   **Planetary Decision Intelligence Platform** — prediction, explanation, historical
   analogue *with divergence*, constrained optimization, and a deployable mission brief
   in one loop. Demo script in `docs/11-demo-devpost-strategy.md`; present it as the
   Operator (gap-closing decision loop), not a feature tour.

## Verification

- `uv run pytest` → **12/12 green** (includes `test_decision_optimizer_strategies_differ` — Alpha protects more lives than Beta; Beta residual loss ≤ Alpha; recommended flag set; inventory caps respected).
- `npm run build` → clean; frontend serving; Next proxy to `/api/v1/decisions/*` confirmed.
- Live demo arc confirmed: hour 48 pulse ~702 watchful → hour 66 pulse ~117 critical; optimiser re-plans as telemetry escalates.