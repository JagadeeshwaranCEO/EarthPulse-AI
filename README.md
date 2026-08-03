```
  _____ _   _ _____ _____ _____  _         _     _____ _      _      ____  ___   ___ ___   _____ _____
 |  ___| | | |_   _|  __ \  ___|/ \     | |   |  ___| |    / \    |___ \/ _ \ / _ \ \ \ / \_   _/ _ \
 | |_  | |_| | | | | |__) |___ \/ _ \    | |   | |_  | |   / _ \     |__| | | || | | \ V  / | || | | |
 |  _| |  _  | | | |  ___/ ___) / ___ \  | |___|  _| | |  / ___ \    | | | |_| || |_| | | |  | || |_| |
 |_|   |_| |_| |_| |_|   |____/_/   \_\ \_____|_|   |_| /_/   \_\   |_|  \___/ \___/  |_|   |_|\___  |

         P L A N E T A R Y   D E C I S I O N   I N T E L L I G E N C E   P L A T F O R M
```

**EarthPulse AI — Planetary Decision Intelligence & Emergency Command Platform.**

[![Build](https://img.shields.io/badge/build-passing-brightgreen)](#tests)
[![Tests](https://img.shields.io/badge/tests-37/37-passing-green)](#run-the-tests)
[![Stack](https://img.shields.io/badge/stack-Next.js_15_%7C_FastAPI-blue)](#tech-stack)
[![AI](https://img.shields.io/badge/XAI-deterministic%2C_no_black--box-6a5acd)](#architecture)
[![Keyless](https://img.shields.io/badge/LLM-keyless_by_default-orange)](#operations--data-integrity)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

Most environmental monitoring tools are **dashboards of failure** — they narrate a disaster
after it has already happened, or hand commanders raw probability percentages that have no
operational meaning.

> **EarthPulse is not an alerting dashboard. It is a decision-support operating system.**
>
> It ingests real-time environmental telemetry, explains *why* a threat is forming,
> measures its own data trust, and runs a constrained multi-objective optimizer that tells
> an Emergency Operations Center **exactly how to deploy finite resources — boats, pumps,
> shelters, budget — to maximize lives saved and minimize economic collapse.**

Built for the operators of the next decade: the people who have minutes, not reports.

---

## 🧠 The Decision-Intelligence Stack

EarthPulse is not a single model. It is a **decision pipeline** — every stage is deterministic,
traceable, and auditable down to the exact formula that produced it:

```
        TELEMETRY ─────────────────────────────────────────────────────────────┐
   (sensors · satellite · rain gauges · citizen)                               │
        │                                                                      │
        ▼                                                                      │
  ┌───────────────┐    ┌─────────────────┐    ┌──────────────────────────┐     │
  │ PREDICTION    │    │ EXPLANATION     │    │ ENVIRONMENTAL MEMORY     │     │
  │ streaming     │    │ formula tracing │    │ vector similarity vs     │     │
  │ forecaster +  │───▶│ + permutation   │──▶│ historical events (2015   │     │
  │ IsolationTree │    │ attribution     │    │ Chennai floods) +         │     │
  │ anomaly score │    │ (SHAP-style)    │    │ divergence & trust        │     │
  └──────┬────────┘    └────────┬────────┘    └────────────┬─────────────┘     │
         │                     │                          │                    │
         ▼                     ▼                          ▼                    │
  ┌────────────────────────────────────────────  ┐
  │  DECISION ENGINE — constrained knapsack       │
  │  optimizer (boats · pumps · shelters · budget)│──── multi-objective Pareto:│
  │  with rainfall-robustness stress sweep        │   Alpha (max lives)        │
  └───────────────────────────────────────────────  └   Beta (shield economy)  │
                                                               Gamma (balanced)│
         │                                                                │
         ▼                                                                ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │ MISSION COMMAND — decision confidence · trade-off matrix · operator    │
  │ execution timeline (T-48 → T-0) · trust pill · AI mission brief (.md)  │
  └─────────────────────────────────────────────────────────────────────────┘
```

**`prediction → explanation → memory → decision → trust → timeline`** — one coherent,
closing story, from raw telemetry to an executable emergency plan.

---

## 🧩 Core Capabilities

**🎯 Predictive XAI Engine** — deterministic anomaly forecasting with exact
formula-tracing and permutation attribution. Every score decomposes into its inputs.
*No black-box LLM guessing. The model can always tell you exactly what it computed and why.*

**⚖️ Multi-Objective Optimizer** — a resource-constrained knapsack solver that trades
*lives saved* against *economic damage* across three Pareto strategies:

| Strategy | Command intent | Objective |
|----------|----------------|-----------|
| **Alpha** | Max lives | Max estimated lives-equivalent impact |
| **Beta**  | Shield the economy | Min residual economic exposure |
| **Gamma** *(recommended)* | Balanced | Lives-weighted economic compromise |

Each candidate plan is stress-tested against **rainfall variance
(+15%, +25%, +40%…)**, reporting a **decision confidence**, a **robustness ratio**, and an
automatic **fallback strategy** if conditions degrade. Optimizer decisions are
deterministic — same inputs, same output, every time.

**🕘 Environmental Memory** — vector-similarity matching against historical climate
events. The engine can say *"this is 78% the 2015 Chennai floods"* — while isolating the
**critical divergences** (drainage dead, pumps saturated) that change the right response
vs that analogue.

**🛰️ Honest Trust Score** — provenance decomposed into six checks (*satellite freshness,
sensor coverage, temporal integrity, historical analogue, model stability, sensor health*).
Rendered as a **live trust pill** (`High` / `Moderate` / `Low / —` ) that visibly *degrades*
as telemetry ages. EarthPulse reports its own confidence.

**🗺️ Precision Satellite Mission Map** — three keyless base channels (*Esri World Imagery /
Maxar, NASA MODIS true color via GIBS, ops vector dark*) plus a **NASA VIIRS analysis
overlay**, 5-decimal coordinate popups, scale bar, hover tooltips, and fine-grained zoom
(0.5-step) up to street resolution. The GIBS date is auto-resolved to the newest archived
pass over the theatre.

**⏱️ Operator Timeline** — the decision engine anchors a **staging, mobilization, lock-down,
impact** sequence to the forecast peak hour — not a wall-clock fiction. Commanders get a
workable **when**, not just a *how many*.

**📋 Auto Mission Brief** — one action exports a dense, operator-facing **Markdown mission
brief**: risk snapshot, causal drivers, trust verdict, tradeoff matrix, allocations,
execution timeline, impacts, actions. Ready to hand to a subordinate.

---

## 🌦️ The Demo Arc — Chennai Flood Command

The live build is calibrated to the **Chennai Metropolitan Area** (15 monitored zones,
synthetic data anchored to the 2015 flood narrative). Operators scrub the synchronized
simulation clock from a **calm build-up (T-48h)** through a **compounding cyclone
(T-0h)** and watch the system **cover-optimize in real time**:

| Phase | Clock | What they enter | System responds |
|-------|-------|-----------------|-----------------|
| Build    | T-48h → T-40h | Planet Pulse dashboard | Anomaly detection escalates, trust **High** |
| Watch    | T-36h → T-24h | Causal explorer | Drivers isolate, satellites aging |
| Decide   | T-24h → T-12h | Resource planner % optimizer | Gamma strategy, decision confidence, fallback, timeline |
| Command  | T-12h → T-0h | Final lock | Mission brief exported, trust scars to **Moderate/Low** |

This is the full decision story — *saw the risk early, explained it clearly, judged its own
trust honestly, chose the best response under constraints, and produced an actionable
plan.* Run this arc live via the Decide & Memory tabs.

---

## ⚙️ Stack

| Layer | Tech |
|-------|------|
| **Frontend** | Next.js 15 · React 19 · TypeScript · Tailwind · glassmorphism mission-control UI |
| **Backend** | FastAPI · SQLAlchemy · NumPy/Pandas · scikit-learn (IsolationTree anomaly) |
| **Optimizer** | Deterministic constrained knapsack solver · Pareto multi-objective (numpy) |
| **Data** | SQLite (local) · Postgres (Docker, optional) · WebSocket sim clock |
| **LLM** | **Keyless by default** — deterministic templates; optional OpenAI live reasoning |

*LLMs never produce raw predictions. Forecasting is exclusively the forecaster +
anomaly detector; the LLM (when enabled) only *verbalizes* the evidence. Deterministic
by default, live optionally.*

---

## 🚀 Quickstart

```bash
# 1. Backend (port 8000)
cd backend && uv sync
uv run uvicorn app.main:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs

# 2. Frontend (port 3000)
cd frontend && npm install
npm run dev
# Mission Control → http://localhost:3000
```

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` and the Next dev server proxies
`/api/*` and `/ws`. Docker Compose runs everything (plus Postgres, optional).

### Run the tests

```bash
cd backend
uv run pytest        # 37/37 green
```

### Operational scope — Chennai ↔ Tamil Nadu ↔ All-India ↔ California ↔ Asia

EarthPulse ships **hazard-templated theatres**. The default is the calibrated
Chennai flood pilot; the state command covers all 38 districts (53 flood-command
zones); the **all-India command covers 80 zones across all 28 states + 8 UTs
on three hazard templates** (39 flood · 23 cyclone · 18 wildfire); a
California wildland-urban-interface pack proves the seam for a second country;
and the **Asia command covers 107 zones on all nine hazard templates** —
earthquake · tsunami · volcanic · landslide · drought · heatwave · flood ·
cyclone · wildfire — across the Ring of Fire, Alpine-Himalayan belt, MENA
heat domes, Indochina dry belts and typhoon alley.

```bash
SCOPE=tamilnadu uv run uvicorn app.main:app --port 8000   # state-wide flood boot
# …or switch live (no restart) from the header, or:
curl -X POST localhost:8000/api/v1/scope -d '{"scope":"tamilnadu"}'
curl -X POST localhost:8000/api/v1/scope -d '{"scope":"india"}'
curl -X POST localhost:8000/api/v1/scope -d '{"scope":"wildfire"}'   # CA wildfire theatre
curl -X POST localhost:8000/api/v1/scope -d '{"scope":"asia"}'       # all-Asia 9-hazard theatre
```

Every zone is stamped with a `hazard_type` (`flood` | `cyclone` | `wildfire` |
`earthquake` | `tsunami` | `volcanic` | `landslide` | `drought` | `heatwave`).
Fusion, history, causal graph, recommendations, evidence templates and risk
levels all dispatch through the hazard registry (`backend/app/hazards/`), so a
scope switch re-runs the **whole pipeline — sensing → fusion → prediction →
explanation → memory → decision — for the new hazard**. Seismic and volcanic
telemetry flows through the `IngestedDatum` archive, keeping the canonical
weather tables untouched.

Seed catalogs: `backend/app/data/seeds/generate_tn_districts.py`,
`generate_india.py` (all states, hazard-typed per regional climatology),
`generate_wildfire.py` (California), `generate_asia.py` (nine hazards across
Asia). See `docs/13-tamilnadu-scaling.md`.

---

## API Surface (`/api/v1`)

| Router | Methods | Purpose |
|--------|---------|---------|
| `/risks` | G | live risk zones, components, forecasts, causal chains |
| `/dashboard` | G | mission-control aggregation, planet pulse |
| `/simulations` | G/P | what-if sandbox, time-scrub, sim clock, damage-ledger |
| `/agents` | G/P | multi-agent diagnostic & debate subsystem |
| `/decisions` | G/P | **optimize · memory · evolution · scientist · trust · mission brief** |
| `/scope` | G/P | live theatre switch — `chennai` ⇄ `tamilnadu` ⇄ `india` ⇄ `wildfire` ⇄ `asia` (reseed + re-run pipeline) |
| `/data` | G/P | ingestion adapters — `sources` (live/demo) · `ingest` (trigger poll) |
| `/chat` | P | grounding-only copilot (never invents readings) |
| `/ws` | WS | live telemetry + sim-clock stream |

The Decision Layer endpoints:
- `POST /decisions/optimize` — strategies Alpha/Beta/Gamma + `analysis` (robustness), `decision_confidence`, `fallback`, `operator timeline`
- `GET /decisions/memory/{location}` — analogue breakdown, matching drivers, critical divergences, reliability
- `GET /decisions/evolution/{location}` — hour-by-hour forecast vs. observational risk
- `GET /decisions/scientist/{location}` — full formula trace + factor weights
- `GET /decisions/trust/{location}` — trust score decomposition (pill)
- `GET /decisions/compare/{location}` — **live comparative analysis**: current telemetry vs. the archived historical record (analogue matches, per-driver deltas, evolution arc, verdict + markdown briefing report)
- `POST /decisions/brief` — mission brief markdown

---

## Directory

```
Earthmark-1
├── backend/           FastAPI + engineering services (forecasting, memory, optimizer)
│   ├── app/
│   │   ├── api/routes/      dashboard · risks · simulations · agents · decisions · chat
│   │   ├── services/        decision_optimizer · environmental_memory · risk_evolution ·
│   │   │                    trust_score · mission_brief · ...
│   │   └── tests/           smoke suite (12)
│   └── pyproject.toml / uv.lock
├── frontend/          Next.js 15 mission-control UI (panels · viz · copilot)
├── docs/              12 design contracts (vision → decision-intelligence layer)
├── scripts/           tooling seeds / CLI
└── docker-compose.yml
```

For the full design contract: `docs/` (01 vision · 02 architecture · 03 AI · 04 UI · 05 data ·
06 API · 07 wireframes · 08 structure · 09 roadmap · 10 risk · 11 demo strategy ·
12 decision-intelligence-layer · 13 tamil-nadu scaling).

---

## 🔬 Data Integrity

- Every pilot reading is **synthetic and provenance-tagged** (`is_synthetic: true`) — the
  system is transparent about what it does and doesn't know.
- Production hooks (IMD, CWPRS, NASA GPM, Copernicus, NDMA) are explicitly declared as
  the intended data sources for deployment.
- All decisions are reproducible math: **same input → same plan, deterministic**.
- **Keyless by default**: the entire pipeline runs without any API key.

---

**EarthPulse is not a dashboard of failure.**
**It is the decision engine for the world's next emergency.**

© 2026 · MIT License