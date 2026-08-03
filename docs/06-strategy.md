# EarthPulse AI — Risk, Demo, Devpost & Startup Strategy

*Document 6/6. Covers deliverables 14–17.*

---

## 1. Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| External data API outage (IMD/CWC/GEE) | Medium | High | Bundled snapshot dataset + synthetic generator (tagged `SYNTHETIC`); demo always runs offline-safe |
| LLM hallucination in explanations | Medium | High | RAG over trusted corpus only; every claim must quote `evidence_id`; UI renders citations; debate verdicts moderated |
| Model performance is weak on real data | High | Medium | V1 is calibrated GBM + physics, not deep learning — honest intervals make weakness visible, not fake; demo replay uses the 2015 flood event where signals are strong |
| Scope creep (wildfire, dumping, copilot...) | High | Medium | Hard feature freeze after Day 11; Day 12 is explicitly lite; anything cut goes to backlog |
| Demo fails live (network, keys, timing) | Medium | High | Scripted 6-minute run with 3 fallback exits; everything demoable from localhost Docker; rehearse 3× before judging |
| Team/time overrun on simulation | Medium | Medium | Simulation is deterministic physics (milliseconds), not ML; Day 9 carries contingency |
| Judge skepticism about AI claims | Medium | Medium | Epistemic humility is the brand: confidence bounds, limitations field, source health bar on screen during demo |
| Credential/secret leakage | Low | High | `.env.example` only; secrets never committed; CI blocks secret patterns |

## 2. Demo Strategy

### 2.1 The story (90 seconds of narrative, 6 minutes total)

> "Dashboards show disasters after they happen. EarthPulse predicts them early, explains them clearly, and simulates how to stop them."

### 2.2 Scripted flow

| # | Action | On-screen wow |
|---|---|---|
| 1 | Open Mission Map, Chennai | 200 wards, amber risk appearing, live telemetry ticking |
| 2 | Click Ward 142 | Risk panel: 68% / SEVERE / 36h / confidence 52–81% |
| 3 | "Why?" → Causal explorer | Rain → Chembarambakkam → Adyar 3.2m → saturation → flood |
| 4 | "How sure?" → Debate | Two agents disagree on the 72h rainfall band; moderator notes data staleness |
| 5 | "What if?" → Sandbox | 4 pumps + sandbags → flood extent −39%, affected 12.4k → 7.6k |
| 6 | Carbon ledger | 412 t CO₂e avoided, $1.6M prevented |
| 7 | Crisis mode | Red command state, operational checklist, dispatch |
| 8 | Evidence trail | 3 citations expand → raw CWC/IMD/GPM payloads |

### 2.3 Demo engineering rules

- Default to **replay mode**: the demo replays the seed 2015 event with live-appropriate latency (telemetry ticks every 2s), so timing never fails.
- Keyboard shortcuts for every jump (1–8 above).
- Crisis mode must hit at minute ~4:30 — the emotional peak before Q&A.

## 3. Devpost Strategy

- **Project name:** EarthPulse AI — Planetary Early Warning Intelligence
- **Tagline:** Predict. Explain. Simulate. — intelligence for the planet.
- **Category pitch:** Best Use of AI for Climate/Disaster Response; also submit for Best Data + Best Design.
- **Submission contents:**
  1. Demo video (90s): map → risk → causal → debate → sandbox → crisis (rehearsed from script 2.2)
  2. 5 screenshots: mission map, causal explorer, sandbox before/after, crisis mode, evidence trail
  3. "Built with" list: Next.js, FastAPI, PostgreSQL+PostGIS, MapLibre, scikit-learn, StatsForecast, GPT-4o/Gemini, D3, Docker
  4. Architecture diagram (from docs/02) + links to this repo
  5. Honesty statement: what is modeled vs simulated vs synthetic (judges reward this)
- **Narrative arc:** problem (2015 Chennai, 500+ deaths, $3B losses) → system → the 8 features → why it's a platform, not a dashboard.

## 4. Startup Strategy

### 4.1 Thesis

Early warning is proven to save lives and money (each $1 invested in early warning returns ~$7–10 in avoided losses — WMO/GFDRR figures; cite in demo). But today's early warnings are *alerts, not decisions*. EarthPulse sells the decision loop.

### 4.2 Beachhead (post-hackathon)

- **Customer:** Tamil Nadu State Disaster Management Authority + Chennai Corporation operations cell.
- **Entry wedge:** pilot "Flood Command" for monsoon season with a retrospective-validation report (how the model would have scored the 2015 event, ward by ward).
- **Expansion path:** Chennai → coastal TN cities (Nagapattinam, Thoothukudi) → state → other flood-prone metros (Mumbai, Hyderabad, Kolkata) → national agencies (NDMA) + insurers (parametric flood insurance needs exactly this: risk + simulation + ledger).

### 4.3 Business model

| Layer | Customer | Offer |
|---|---|---|
| Gov SaaS | Disaster mgmt authorities | Command center + crisis mode + audits |
| Insurer data | Parametric/ P&C insurers | Risk scores, simulation API, ledger for premiums |
| Enterprise | Ports, utilities, logistics | Custom regions + escalation |
| Public good | Citizens | Free crisis alerts (brand + reach) |

### 4.4 Moat recap

1. Causal + simulation loop competitors don't have
2. Epistemic honesty as trust brand (regulators/govs value it)
3. Provenance-by-architecture (auditable by design)
4. Open-data cost structure (no proprietary satellite costs at V1)

### 4.5 What NOT to do

- Don't build a consumer app.
- Don't claim "AI predicts floods" — claim "explainable early warning for decisions."
- Don't expand geographies before the Chennai retrospective validation is published.
- Don't charge money before one monsoon season of trusted operation.

---

*Execution package complete. Begin implementation with docs/05 Day 1.*
