# 08 — Folder Structure

```
Earthmarkone/
├── README.md
├── docker-compose.yml
├── .env.example
├── docs/                      # design contract (01–11)
├── backend/
│   ├── pyproject.toml         # uv-managed
│   ├── app/
│   │   ├── main.py            # FastAPI app factory + lifespan seed
│   │   ├── config.py          # env-driven settings
│   │   ├── core/
│   │   │   ├── db.py          # engine/session (sqlite dev, postgres prod)
│   │   │   └── models.py      # SQLAlchemy entities
│   │   ├── schemas.py         # Pydantic API contracts
│   │   ├── api/
│   │   │   ├── routes/        # dashboard, risks, predictions, simulations,
│   │   │   │                  # recommendations, agents, chat, pulse
│   │   │   └── ws.py          # live tick websocket
│   │   ├── agents/            # 11 agents + base + orchestrator + debate
│   │   ├── ml/                # forecaster, anomaly, attribution, pulse
│   │   ├── services/          # llm, simulation_engine, evidence, copilot
│   │   └── data/seeds/        # chennai_seed.json (provenance-tagged)
│   └── tests/                 # smoke tests for pipeline
├── frontend/
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── page.tsx           # mission control
│   └── components/
│       ├── map/MapView.tsx
│       ├── panels/            # RiskList, RiskDetail, CausalChain,
│       │                      # SimulationSandbox, DebatePanel, Copilot,
│       │                      # EvidencePanel, AttributionPane
│       ├── viz/               # PulseGauge, ConfidenceMeter, Timeline,
│       │                      # ForecastChart
│       └── ui/                # Panel, Tabs, Badge, CrisisBanner
└── scripts/seed_demo.py       # regenerate/import demo data
```
