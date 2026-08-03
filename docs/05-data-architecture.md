# 05 — Data Architecture

## Entities (SQLAlchemy models)

`locations`, `events`, `alerts`, `predictions`, `sources`, `weather_snapshots`,
`satellite_frames`, `citizen_reports`, `interventions`, `simulation_runs`,
`evidence_objects`, `agent_messages`, `pulse_scores`.

## Provenance rule

Every `Prediction` and `Alert` rows reference `evidence_objects[]`; each evidence
object carries `source_id`, `captured_at`, `license`, `url`, `description`. A risk
score without provenance is not emitted.

## Seed dataset: Chennai flood command

Realistic synthetic dataset anchored to the 2015 Chennai floods narrative and real
institutions (IMD rainfall, CWPRS levels, NASA GPM, Copernicus, civic body alerts):

- 15 zones around Chennai (lat/lon, elevation, drainage capacity)
- 96 h of rainfall at 15-min resolution (NE monsoon onset)
- Adyar / Cooum / Otteri canal water levels + headroom
- Satellite soil-moisture anomaly series
- ~40 citizen reports, ~20 news items with credibility

All rows flagged `is_synthetic=True` in their provenance — transparency by default.

## Extension points

Wildfire (`vegetation_fuel`, `humidity`, `wind`) and illegal dumping
(`night_light_anomaly`, `report_density`) schemas exist as feature fields on
`events` + `evidence` tags, ready for secondary modules.
