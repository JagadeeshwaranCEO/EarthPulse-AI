# 15 — India → Asia: decision-support OS, phased

EarthPulse is not an alerting dashboard. It is a **decision-support operating
system for disaster command**: forecast-aware, basin-aware, action-aware, and
command-ready — built to be trusted by the people who move people.

The current product scores zones as hazards. The target product connects zones
to **systems** (rivers, drains, pumps, embankments, shelters, roads), stages
**actions**, and speaks the language of **command** (lead time, confidence,
cost, lives). This doc fixes the build order.

---

## Phase 1 — Lead-aware forecast core ✅

The forecast must be **lead-aware, not history-aware**: an incoming storm ramp
that already exists in the rain forecast must not wait for observed
accumulation to show up in risk.

Done in this slice:

- **Two-stage nowcast** (`backend/app/services/nowcast.py`): Stage A fuses
  forward signals (rain_forecast_mm, upstream inflow, soil-saturation memory)
  into a lead-aware driver state; Stage B converts it into a risk **ladder at
  +1/+3/+6/+12/+24h**, each rung with a confidence band and a **reason trail**.
  Forecast influence ramps to its +6h validity then *holds* (persistence) — an
  incoming storm is never silently smoothed away at +12/+24h.
- **Prediction agent** (`cognition.py`) emits `lead_ladder` + `peak_in_h`;
  exposed on `GET /api/v1/risks/{id}/prediction`.
- **Honest verification** (`services/verification.py`): scores the *actual
  ladder* on a rolling holdout (issuance t0∈{12,24,36,48}, targets t0+{1,3,6,12,24})
  vs realized telemetry. Brier **0.102 → 0.031**, AUC **0.63 → 0.76**, tiers
  upgraded from all-C to B/C. Reports reliability table, sharpness, and a
  **calibration gap** (`mean_forecast − mean_realized`) instead of a vanity
  BSS sign — current gap ≈ −0.06, i.e. the system still under-forecasts peaks.
- **Short-history honesty** (`ml/forecaster.py`): zero-padding a young series
  fabricated trend (0.05 → 0.6+); now pads on the first value, no fake slope.

Why the gap is negative and what that teaches: the demo feed
(`rain_forecast_mm` = +6h) bounds lead-awareness at 6 hours; beyond that the
ladder holds via persistence. Under-forecast concentrates exactly at the storm
ramp — the moments that matter. A static probability recalibration does **not**
fix a time-dependent offset (tested, out-of-sample it made Brier worse) — the
real fix is a **longer-horizon forecast feed** (IMD/ECMWF multi-day QPF,
Phase 3).

## Phase 2 — Zones → systems

Give every zone its operative skeleton so recommendations become concrete:

- **River graph** per basin (reach, junction, upstream/downstream, bank
  elevation); water level → **hours-to-breach** per reach.
- **Drainage + pumps**: stormwater network capacity, pump station duty,
  **outage/lives exposed** when capacity is exceeded.
- **Embankments**: design return level, inspection state, breach-pressure
  rating.
- **Shelters**: capacity, population in catchment, evacuation routing.
- **Road blockage risk**: underpass/low bridge flooding, detour time.
- **Command brief** + **audit log**: who saw what, when, and what was done.

## Phase 3 — India-ready, multi-hazard

- Hazard depth for **cyclone, heatwave, landslide, drought** (forecast feeds +
  India-specific causal chains), common multi-hazard framework.
- **IMD/NDMA/SMS**: real feeds through `ingest/` adapters, SMS/WhatsApp/IVR
  outbound, NDMA-style sitrep/state bulletins.
- **Multilingual UI** + **offline-first** for district HQ connectivity.
- Multi-day QPF into the forecast core → closes the Phase 1 gap.

## Phase 4 — Asia ontology

Common hazard framework; region templates (SE Asia monsoons, Japan typhoon,
Pacific cyclone, HK typhoon signal-style levels); country adapters on the same
scoring core. `asia` scope already registered with 107 zones (9 templates).

---

## Positioning

> **A decision-support operating system for disaster command.** Forecasts you
> can act on, basins you can run, actions you can stage, and a paper trail
> command can defend. Built India-first, scaled Asia-wide.
