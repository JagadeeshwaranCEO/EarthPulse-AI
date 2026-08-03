# EarthPulse AI — Product Vision & Specification

*Document 1/6 of the execution package. Covers deliverables 1–5: product vision, product specification, feature list, user journeys, competitive positioning.*

---

## 1. Product Vision

**One line:** Palantir for Planet Earth — predict environmental risk early, explain why it is happening, and simulate how to stop it.

**The problem:** Dashboards show disasters after they happen. Flood early-warning systems broadcast a red alert but cannot tell an operations officer *why* the risk is forming, *what happens if they act*, and *how much damage an intervention avoids*. Decision-makers drown in data but starve for decisions.

**The product:** EarthPulse AI is a planetary intelligence layer that takes satellite, weather, sensor, citizen, and news signals; fuses them into a unified regional risk picture; explains every score through a causal chain and evidence trail; and lets operators simulate interventions before committing resources.

**The moat:** prediction + explanation + simulation + edge sensing, in one system, with every output traceable. Not a chart product. Not decorative AI. A decision system.

## 2. Product Specification (V1)

### 2.1 Flagship scenario: Flood Command — Chennai pilot

| Attribute | Value |
|---|---|
| Geography | Chennai, Tamil Nadu, India (200 wards, Adyar + Cooum river basins, Chembarambakkam lake catchment) |
| Risk type | Urban flash + riverine flooding (2015 Chennai floods as reference event) |
| Time horizon | 0–72 hour forecasts, refreshed every 15 min |
| Primary users | City operations officer, disaster management cell, citizen |
| Secondary modules | Wildfire risk (lite), illegal dumping detection (lite) |

### 2.2 Non-negotiable principles

1. **Epistemic humility** — every prediction ships with confidence score, uncertainty bounds, data sources, and known limitations.
2. **Simulation over observation** — risk is never shown without a causal chain, intervention options, and before/after impact.
3. **Scientific validity** — specialized models (time-series, spatiotemporal) for forecasting and anomaly detection. LLMs only for explanation, reasoning, summarization, and action planning.
4. **Trust through transparency** — every score is explainable via feature attribution, supporting evidence, source citations, and traceable reasoning.
5. **Build for reality** — demoable in a hackathon, architected like a platform.

### 2.3 Success criteria

- A non-expert can open the map and answer in 60 seconds: *is my area at risk, why, and what should I do?*
- A scientist can trace any risk score to its raw data and model inputs.
- An operator can simulate an intervention and see the predicted damage reduction.
- Every AI output is backed by an evidence object with provenance.

## 3. Feature List (V1)

### Core (P0)
1. Interactive city map with ward-level flood risk overlay
2. Risk detail panel: probability, severity, time horizon, confidence, uncertainty bounds
3. Causal chain explorer (node graph: rain → soil saturation → river stage → flood)
4. AI explanation pane with feature attribution (SHAP) and citations
5. What-if simulation sandbox (interventions → predicted impact)
6. Operational checklist + alert priority (Recommendation layer)
7. Evidence / provenance view

### Differentiators (P1)
8. AI Debate Engine (two agents argue conflicting evidence when confidence is low)
9. Planet Pulse Score (0–1000 regional stability metric with breakdown)
10. Time-scrubbing digital twin (risk propagation across past/future)
11. Crisis Command Center mode (high-alert visual state)
12. Carbon Impact Ledger (damage prevented → emissions avoided)

### Secondary modules (P2, lite)
13. Wildfire risk index (dryness + temperature + wind)
14. Illegal dumping detection (anomaly flags on citizen/satellite signals)

### Platform (P0)
15. Ingestion: weather, river gauge, satellite, citizen reports, news
16. Data provenance for every score
17. Model versioning + audit trail
18. Live telemetry (WebSocket) for the dashboard

## 4. User Journeys

### 4.1 City operations officer — the morning briefing
1. Opens EarthPulse, sees Chennai map with amber flood overlay on 3 wards.
2. Opens the top ward → risk panel: 68% probability in 36h, severity HIGH, bounds 52–81%.
3. Opens causal chain: *GPM rainfall 180mm/24h → Chembarambakkam outflow 12,000 cusec → Adyar river stage 3.2m → ward X drainage saturation*.
4. Opens What-If sandbox, deploys 4 mobile pumps + pre-positions sandbags → predicted flood extent −38%, affected population 12k → 4.1k.
5. Approves checklist. Sends alert. Cites the evidence trail in the daily report.

### 4.2 Citizen during crisis
1. Receives SMS: "Ward 142 — flood risk HIGH in 12h. Evacuation route maps at earthpulse/142."
2. Opens Crisis mode on phone: red state, evacuation checklist, live shelter map, pump status.
3. Confidence meter is visibly honest ("uncertainty high — satellite cloud cover 70%").

### 4.3 Researcher / scientist
1. Pulls a risk score for June 2025 event.
2. Traces → model version `flood-rf-v3` → feature SHAP values → source records (CWC gauge readings, IMD rainfall).
3. Runs their own counterfactual in the sandbox. Exports the audit trail.

### 4.4 Policy maker
1. Asks copilot: "What would a green-infrastructure retrofit along the Adyar do over 5 years?"
2. Simulation runs across 5 historical rainfall scenarios; shows damage reduction curve + carbon ledger.
3. Exports the output for the budget presentation.

## 5. Competitive Positioning

| Player | Strength | Gap EarthPulse fills |
|---|---|---|
| Google Flood Hub | Global flood forecasting at scale | No causality, no simulation, no intervention planning |
| Jupiter Intelligence | Financial-grade climate risk data | Enterprise-only, no live operations dashboard, closed |
| Tomorrow.io | Weather API + radar | Weather, not *consequence* intelligence |
| One Concern | Seismic + flood resilience | Closed models, no causal transparency |
| Descartes Labs | Satellite analytics | Data platform, not a decision system |
| IBM PAIRS | Geospatial data fusion | Analyst tool, not an early-warning product |

**EarthPulse positioning:** "Google Flood Hub tells you *it will flood*. EarthPulse tells you *why*, *what happens if you act*, and *how much you saved* — in one traceable, open-data system."

**Moat:** the causal-chain + simulation + provenance loop. Competitors own one layer; EarthPulse owns the full decision loop with epistemic honesty as a brand.

---

*Next: docs/02-architecture.md*
