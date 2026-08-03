# EarthPulse AI — Folder Structure & 13-Day Build Plan

*Document 5/6. Covers deliverables 12–13.*

---

## 1. Repository Folder Structure

```
earthpulse/
├── README.md
├── docker-compose.yml            # postgres+postgis, minio, api, web
├── Makefile                      # make dev / make seed / make demo
├── .env.example
├── docs/                         # this execution package
├── apps/
│   ├── web/                      # Next.js 14 + TS + Tailwind + MapLibre
│   │   ├── app/
│   │   │   ├── (mission)/
│   │   │   │   ├── page.tsx            # Mission Map
│   │   │   │   ├── crisis/page.tsx     # Crisis Command Center
│   │   │   │   └── pulse/page.tsx      # Pulse + history
│   │   │   └── api/                    # BFF proxies (optional)
│   │   ├── components/
│   │   │   ├── map/            (MapView, WardLayer, FloodOverlay)
│   │   │   ├── panels/         (RiskPanel, TelemetryStrip, EvidenceList)
│   │   │   ├── explain/        (CausalGraph, ShapBars, DebateView)
│   │   │   ├── simulate/       (SimulationPanel, CarbonLedger)
│   │   │   └── ui/             (design tokens, chips, meters)
│   │   ├── lib/                (api client, ws client, format utils)
│   │   ├── styles/             (tokens.css, globals.css)
│   │   └── public/
│   └── api/                    # FastAPI
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── db.py           # SQLAlchemy engine/session
│       │   ├── models/         # ORM models (mirror docs/02 schemas)
│       │   ├── routers/        # health, risk, causal, explain, simulate,
│       │   │                   # recommend, pulse, ledger, reports, copilot, jobs
│       │   ├── services/       # prediction, simulation, explanation, pulse
│       │   ├── ws.py           # pub/sub hub + /ws/live
│       │   └── schemas/        # Pydantic contracts
│       └── tests/
├── services/                   # worker processes (agents & collectors)
│   ├── agents/
│   │   ├── base.py             # Agent ABC: mission/inputs/outputs/confidence/failure
│   │   ├── bus.py              # Postgres-backed message bus
│   │   ├── weather_agent.py    # IMD + GPM IMERG
│   │   ├── gauge_agent.py      # CWC river stage
│   │   ├── satellite_agent.py  # Sentinel-1 via GEE (fallback synthetic)
│   │   ├── citizen_agent.py    # report intake + clustering
│   │   ├── news_agent.py       # GDELT
│   │   ├── fusion_agent.py     # weighted fusion + provenance
│   │   ├── prediction_agent.py # forecast + calibrate
│   │   ├── explanation_agent.py# SHAP + RAG narrative
│   │   ├── recommendation_agent.py
│   │   ├── simulation_agent.py
│   │   └── debate.py           # on-demand debate orchestration
│   └── ingestion/
│       ├── collectors/         # weather.py, gauge.py, satellite.py, news.py
│       └── synthetic.py        # demo data generator (tagged SYNTHETIC)
├── packages/
│   ├── models/                 # shared TS types (frontend ↔ API contract)
│   └── earthpulse-sdk/         # Python client lib for the API
├── data/
│   ├── raw/                    # downloaded datasets + imagery
│   ├── processed/
│   └── scripts/                # etl.py, seed.py, train_flood_model.py
├── infra/
│   ├── postgres/init.sql       # DDL from docs/02
│   └── observability/          # prometheus.yml, grafana provisioning
└── .github/workflows/ci.yml    # lint + typecheck + tests
```

## 2. Build Principles

- One module at a time, demo-visible after each day.
- Data > models: the dataset script lands on **Day 2**, everything consumes it.
- Every AI feature hits the API before the UI.
- "Demo-first, platform-always": fake nothing structurally, but synthetic fallbacks are tagged.

## 3. The 13-Day Plan

| Day | Focus | Deliverable (demo-visible) | Key decisions |
|---|---|---|---|
| 1 | **Platform skeleton** | Repo + Docker Compose up (PostGIS + MinIO + API + web) + design tokens + CI | Stack locked: Next 14 / FastAPI / PostGIS / MapLibre |
| 2 | **Data spine** | `data/scripts/etl.py` + seed → Chennai 200 wards, basins, CWC gauges, IMD/GPM rainfall history, SRTM-derived ward wetness | Data > models; synthetic generator ready |
| 3 | **Schema + API core** | Postgres DDL (`infra/postgres/init.sql`) + `/health`, `/regions`, `/risk/summary` with real seeded geometry | Provenance contract: every score must carry evidence |
| 4 | **Prediction layer** | Flood model (GBM + hydro features + isotonic calibration) + `/risk/{ward_id}` + `/risk/timeseries` | Model registry `flood-gbm-v3`; intervals from StatsForecast |
| 5 | **Anomaly + fusion** | Isolation Forest anomalies + fusion agent consuming collector outputs + `/sources/status` | LLM still absent — system already tells a story |
| 6 | **Explanation layer** | SHAP + causal chain builder + `/causal/{event_id}` + `/explain/{risk_id}` (RAG narrative w/ citations) | LLM scoped to explanation only |
| 7 | **Frontend mission map** | MapView + ward severity layer + RiskPanel + ConfidenceMeter + telemetry strip (WS) | Dark mission-control design system live |
| 8 | **Causal + debate** | CausalGraph (D3) + DebateView + `/debate` + EvidenceList | Debate triggers only when confidence < threshold |
| 9 | **Simulation** | Hydro what-if engine + `/simulate` + SimulationPanel with before/after + Carbon Ledger | Deterministic physics; uncertainty bounds shown |
| 10 | **Pulse + recommendations** | Pulse engine `/pulse` + TimeScrubber + ChecklistCard + `/recommendations` | Pulse components expose their weights |
| 11 | **Crisis mode + copilot** | Crisis Command Center full-screen + `/copilot/chat` + alert dispatch | Crisis = story climax; copilot grounded in evidence |
| 12 | **Secondary modules (lite)** | Wildfire index (dryness/temp/wind) + illegal dumping anomaly flags | Stub honest: labeled "experimental" in UI |
| 13 | **Demo hardening** | Scripted demo run-through, seed 2015-flood replay scenario, performance pass, README, Deploy to Vercel+Railway/Fly | Freeze scope. Polish motion. Rehearse the 6-minute story |

### 3.1 Critical path & buffers

- **Hard dependencies:** Day 2 → 3 → 4 → 6 → 8; Day 7 → 9; Day 11 depends on 8+9.
- **Flexible:** Day 5 and Day 12 can compress to half-days.
- **Risk buffer:** Days 6 and 9 each carry a half-day contingency; if a day slips, cut Day 12 features first, then debate polish — never the demo story arc.

### 3.2 Definition of done (each day)

1. Code merged to main, CI green.
2. Feature callable via API (or rendered in UI for UI days).
3. Feature demonstrable in ≤60 seconds.
4. Any AI output shows evidence IDs + model version.

---

*Next: docs/06-strategy.md*
