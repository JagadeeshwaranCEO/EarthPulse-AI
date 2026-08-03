# 13 — Tamil Nadu Scale Layer

The Chennai pilot (15 zones) is the calibration theatre; this layer makes EarthPulse
a **state-wide decision platform**. Same pipeline, two operational scopes, live
switchable, with a real-data ingestion contract and a retrospective calibration
harness so "precision" is measured, not claimed.

## 1. Operational scopes

| Scope | Zones | Seed | Use |
|-------|-------|------|-----|
| `chennai` *(default)* | 15 | `chennai_seed.json` | 5-minute pilot demo, calibrated arc |
| `tamilnadu` | 53 (15 + 38 district HQs) | `tamilnadu_seed.json` | state command — all 38 districts |

- Boot scope: `SCOPE=tamilnadu uv run uvicorn app.main:app --port 8000` (empty DB).
- **Live switch** (no restart): `POST /api/v1/scope {"scope":"tamilnadu"}` — wipes
  location-scoped rows, reseeds, re-runs the pipeline. UI: header toggle
  `deploy tamil nadu`.
- District catalog: `app/data/seeds/generate_tn_districts.py` — one flood-command
  anchor per district HQ with real geometry, elevation, and population; NE-monsoon
  trough tracks south→north along the coast (coastal/low-lying districts peak
  first and hardest). Every zone carries a `region` tag surfaced in the UI.

## 2. Real-data ingestion adapters

`app/services/ingest/` defines the seam where live telemetry attaches:

| Adapter | Live endpoint (when set) | Writes to |
|---------|--------------------------|-----------|
| `imd`   | `IMD_ENDPOINT` (+`IMD_TOKEN`) `GET /rainfall?station=` | `weather_snapshots` |
| `gpm`   | `GPM_ENDPOINT` (+`GPM_TOKEN`) `GET /precip?lat=&lon=` | `satellite_frames` |
| `reservoir` | `RESERVOIR_ENDPOINT` (+`RESERVOIR_TOKEN`) `GET /reservoirs?district=` | `ingested_data` archive |

- **Demo mode (default):** no credentials → deterministic, provenance-tagged
  synthetic frames derived from each zone's own telemetry; `is_synthetic=True`.
- **Live mode:** configure the endpoint → the adapter fetches real data and writes
  under `*-live` source ids; provenance reflects *real*.
- Trigger: `POST /api/v1/data/ingest` · status: `GET /api/v1/data/sources`.
- The pipeline's feature tables (`weather_snapshots`, `satellite_frames`) are what
  the forecaster reads, so live rainfall/soil frames flow straight into risk.

## 3. Calibration harness

`backend/scripts/calibrate.py` → `backend/calibration_report.json`

Replays stored historical flood signatures (outcome=occurred) + calm counterfactuals
(outcome=no flood) through the **same deterministic** probability function used in
production, then reports:

- **Brier score** (before / after recalibration)
- **Reliability diagram** (mean-prediction vs observed-frequency per bin)
- **Platt-style recalibration fit** (`logit p' = bias + slope·logit p`) — advisory
  until wired into production (flag `applied_to_production: false`)

Honest framing: with synthetic signatures this validates *internal consistency*;
the same harness becomes externally meaningful the moment a real feed + ground-truth
event log is attached — which is exactly what the ingestion layer provisions.

## 4. Verification

```bash
cd backend
uv run pytest        # 18/18 (smoke 12 + scale 6)
uv run python -m scripts.calibrate
curl -X POST localhost:8000/api/v1/scope -d '{"scope":"tamilnadu"}'
```
