# 14 · Hazard Template Registry & Global Scaling

*Slice 1 of the world-scale roadmap: the codebase becomes hazard-parametric before
it becomes geography-parametric. A new hazard theatre is now a data-pack, not a
code rewrite.*

---

## 1 · What changed

EarthPulse is no longer a flood platform that happens to be located in Chennai.
Every zone carries a `hazard_type` (`flood` | `cyclone` | `wildfire` |
`earthquake` | `tsunami` | `volcanic` | `landslide` | `drought` | `heatwave`),
and the **entire decision pipeline dispatches through a hazard registry** —
sensing, fusion, prediction, explanation, recommendation, evidence, evolution
and memory all resolve the active hazard first.

**New hazard in one seat:** add a `HazardSpec` to `app/hazards/`, register it in
`app/hazards/registry.py`, ship a seed pack for the scope — the pipeline, UI,
comparative analysis and trust score adapt without further edits.

## 2 · Architecture

```
app/hazards/
  spec.py      HazardSpec dataclass — fusion/history/formula/features/hourly/
               causal/recommend/interventions/evidence/thresholds/scale
  flood.py     FLOOD  — weights 1.0/0.8/1.2/0.7/0.3, scale 52, thresholds .75/.55/.3
  wildfire.py  WILDFIRE — fuel dryness + aridity + wind + thermal, scale 46,
               thresholds .8/.6/.35 (stricter high band: fire risk is faster)
  cyclone.py   CYCLONE — wind + surge + rain-band drivers, scale 48,
               thresholds .8/.6/.35; India's coastal high-speed hazard
  earthquake.py EARTHQUAKE — seismic episode monitor (accel + energy release),
               scale 44; not a day-of-quake forecast — aftershock/damage risk
  tsunami.py   TSUNAMI — offshore seismic source + sea-surface disturbance,
               scale 44; the actionable lead window after a sea-floor event
  volcanic.py  VOLCANIC — tremor + SO2 flux + ash plume escalation, scale 44
  landslide.py LANDSLIDE — slope saturation + burst trigger, scale 46
  drought.py   DROUGHT — precipitation deficit + soil desiccation, scale 44
  heatwave.py  HEATWAVE — thermal excess + stagnation + dry-bulb load, scale 46
  registry.py  HAZARDS dict (9 templates), get_hazard() with flood fallback
  levels.py    level_for(hazard_id, p) — hazard-scoped severity bands
```

Seismic / volcanic telemetry (`ground_accel`, `seismic_energy`,
`volcanic_tremor`, `so2_flux`, `ash_plume_km`) flows through the
`IngestedDatum` archive — `seeder.py` accepts a per-zone `seismic` list and the
orchestrator loads it into `payload["seismic"]`, so the canonical weather
tables stay untouched and every row keeps its synthetic provenance flag.

Dispatch seams:

| Layer | Mechanism |
|-------|-----------|
| Sensors | `WeatherAgent` emits `wind_kmh` + `rain6_mm` beside flood drivers |
| Fusion | `RiskFusionAgent` → `hazard.fusion(payload)` |
| Prediction | `probability_for(hazard, components)`; `probability_from_components` kept as flood alias |
| Explanation | `hazard.causal(components, pred)` |
| Recommendation | `hazard.recommend(p, severity)` |
| Evidence | `hazard.evidence` templates (`noaa-firewx`, `viiirs-thermal`, `imd-cyclone`, `civic-reports`, `news-eom`) |
| Evolution | `hour_components(hazard_id, …)` + `hazard.probability` / `hazard.level` |
| Memory | `environmental_memory` is hazard-typed — cyclone zones match cyclone signatures, wildfire zones match fire events |
| Dashboard/risks | summaries query `Prediction` by `loc.hazard_type`; levels via `level_for` |
| Seeder | interventions merged from the whole registry; `hazard_type` stamped per zone |

## 3 · The All-India command theatre

`backend/app/data/seeds/generate_india.py` → `india_seed.json`:
**80 zones covering all 28 states + 8 UTs**, hazard-typed per regional
climatology on all three templates (39 flood · 23 cyclone · 18 wildfire):

- **Cyclone belt** — Bay of Bengal (Sundarbans, Balasore, Puri, Kakinada,
  Nagapattinam, Rameswaram) and Arabian Sea (Kutch, Surat, Raigad, Alappuzha,
  Karwar) plus island UTs. Storm wind ramps to 55–62 km/h by landfall hour,
  track-proximity scaled so the surge lead zones (Sundarbans, Kavaratti) run
  hotter than the capitals.
- **Flood plain** — Ganges/Brahmaputra basins (Prayagraj, Varanasi, Bihar
  districts, Kaziranga, Kolkata, Delhi Yamuna belt) with monsoon bursts that
  peak hardest in Bihar/Assam (55 mm vs plateau 40 mm).
- **Wildfire belt** — Himalayan fir/deciduous districts (Nainital, Kangra,
  Dehradun, Shimla) + central dry-deciduous (Balaghat, Dantewada, Hazaribagh,
  Gadchiroli, Nagaland hills). Humidity collapses toward 25%, wind ramps.

Live check:
`curl -X POST localhost:8000/api/v1/scope -d '{"scope":"india"}'` → 80 zones;
a cyclone coast zone reports "resembles Bay of Bengal cyclone (Oct 2019)",
a Ganges zone reports "NE monsoon inundation (Nov 2021) at 75%" — hazard-scoped
analogues, computed not narrated.

## 4 · The California wildfire theatre

`backend/app/data/seeds/generate_wildfire.py` → `wildfire_seed.json`:
5 wildland-urban-interface zones (Santa Rosa, Paradise, Mariposa foothills,
LA Basin Rim, San Diego backcountry) under a heat-dome red-flag arc:

- humidity 55% → 21%, wind 14 → 45 km/h, rain ≈ 0–2.5 mm
- soil-moisture anomaly 4.2 → 0.6 (dying wetness = rising fuel dryness)
- 60 verified smoke/flame sightings through `civic-reports`
- real event names (Tubbs, Camp, Woolsey, Cedar) with synthetic signatures

Live check: `curl -X POST localhost:8000/api/v1/scope -d '{"scope":"wildfire"}'`
→ 5 zones, all *high/critical* at peak hour; comparative analysis reports
"resembles Camp Fire (Nov 2018) at 57%" — computed similarity, not narration.

## 5 · The All-Asia command theatre

`backend/app/data/seeds/generate_asia.py` → `asia_seed.json`:
**107 zones on all nine hazard templates**, spanning the tectonic and climate
belts of Asia (14 earthquake · 12 tsunami · 11 volcanic · 10 landslide ·
14 drought · 13 heatwave · 15 flood · 10 cyclone · 8 wildfire):

- **Seismic episode belt** — Tokyo, Sendai, Hualien, Jakarta, Padang, Manila,
  Kathmandu, Quetta, Tehran, Istanbul, Chengdu: mainshock ~60% through the
  window with an Omori-style aftershock energy tail through `seismic_energy`
  and `ground_accel` telemetry.
- **Tsunamigenic coasts** — Banda Aceh, Palu, Kochi, Miyagi, Colombo, Galle,
  Cox's Bazar, Phuket: one large offshore energy release, surge lead zone
  exposure 1.4–1.55.
- **Volcanic escalation** — Merapi, Sinabung, Agung, Krakatoa watch, Mayon,
  Taal, Pinatubo, Sakurajima, Kamchatka: tremor + SO2 flux ramp from ~45%,
  ash plume lifts late (`volcanic_tremor`, `so2_flux`, `ash_plume_km`).
- **Monsoon slope belt** — Pokhara, Thimphu, Badulla, Baguio, Bogor,
  Wenchuan, Muzaffarabad: saturation + burst-trigger physics with steeper
  peaks than plain flood zones.
- **Dry belts** — Karachi/Hyderabad Sindh, Jaffna, Khon Kaen, Xi'an loess,
  Kerman, Kabul, Ulaanbaatar (drought); Baghdad/Basra/Ahvaz/Kuwait/Doha/Dubai
  heat domes plus Lahore/Multan, Shanghai/Wuhan, Seoul/Daegu (heatwave).
- **Monsoon rivers + typhoon alley** — Dhaka/Sylhet/Barisal, Hanoi/Ho Chi
  Minh, Bangkok, Guangzhou, Sukkur (flood); Samar, Catanduanes, Da Nang,
  Khulna, Hainan, Okinawa (cyclone); Indonesian peat haze + Chiang Mai smog
  bowl + Siberian taiga (wildfire).

Live check: `curl -X POST localhost:8000/api/v1/scope -d '{"scope":"asia"}'`
→ 107 zones, 107 predictions, 107 alerts; Tokyo Bay reports an active seismic
episode (~63% high), Merapi runs *critical* (~90%) on tremor/SO2 escalation.

## 6 · Flood parity guarantee

The refactor preserves flood behavior bit-for-bit:

```
probability_from_components(c) ≡ get_hazard("flood").probability(c)   # < 1e-12
```

`tests/test_hazards.py::test_flood_forecaster_dispatch_is_bit_identical` guards
this permanently. Wildfire curve is monotonic in every driver (calm 0.08 →
extreme 0.89) and cyclone wind carries the largest marginal weight — both under
test.

## 7 · Next slices on the world-scale roadmap

1. **Inter-hazard coupling** — cyclone → flood cascade; the causal graph
   already models per-hazard edges.
2. **Geography-parametric seeding** — regions declare zones + telemetry arcs
   (the `india` and `asia` packs are already exactly that shape at country scale).
3. **Live global feeds** — the scope endpoints stay the same; only the adapter
   source changes.

## 8 · Schema note

`Location.hazard_type` (VARCHAR, default `'flood'`) is the only new column.
SQLite dev DBs created before this slice need
`ALTER TABLE locations ADD COLUMN hazard_type VARCHAR DEFAULT 'flood';`
(or just delete the dev DB — every theatre reseeds from synthetic packs).
