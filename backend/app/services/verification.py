"""Forecast verification engine — honest, computed precision.

The platform claims explainability; this module verifies that claim. It runs a
rolling pass over the seed telemetry: for every zone, forecasts issued at
hours {12, 24, 36, 48} for horizons {6, 12, 24} are scored against the
*realized* risk at the target hour — realized meaning the same hazard formula
applied to the telemetry that actually unfolded. Nothing narrated: every
number below is computed.

Metrics (per hazard, per zone, overall):
- Brier score          mean((forecast - realized)^2)
- Brier skill (BSS)    1 - Brier / Brier_climatology  (climatology = base rate)
- ROC AUC              Mann-Whitney on (forecast, realized>=high-band)
- Reliability table    forecast deciles vs observed event fraction
- Sharpness            mean band width at issuance (precision of the bands)
- Tier                 A/B/C from BSS — the per-zone precision grade
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from app.core.models import Location, SatelliteFrame, WeatherSnapshot
from app.ml.forecaster import DEFAULT_FORECASTER
from app.services.nowcast import LEADS, components_ahead, signal_from_weather
from app.services.risk_evolution import hour_components
from app.services.ticker import current_hour

STARTS = (12, 24, 36, 48)
HORIZONS = LEADS
RELIABILITY_BINS = np.linspace(0.0, 1.0, 11)

_CACHE: dict[tuple, dict] = {}


def _cache_key(db, scope: str | None) -> tuple:
    first = db.query(Location).first()
    scope = scope or (first.region if first else "?")
    n = db.query(Location).count()
    n_rows = db.query(WeatherSnapshot).count()
    return (scope, n, n_rows, current_hour())


def _realized(db, loc: Location, hazard, weather: list[dict], sat: list[dict], hour: float) -> float:
    comps = hour_components(hazard.id, weather, sat, hour, _exposure(loc), loc.drainage_capacity_mmh)
    return float(hazard.probability(comps))


def _exposure(loc: Location) -> float:
    return float((loc.attributes or {}).get("exposure", 1.0))


def _band_width(fc) -> float:
    if fc is None or not fc.upper:
        return 0.0
    return float(np.mean(np.asarray(fc.upper) - np.asarray(fc.lower)))


def _auc(scores: list[float], events: list[int]) -> float | None:
    pos = [s for s, e in zip(scores, events) if e == 1]
    neg = [s for s, e in zip(scores, events) if e == 0]
    if not pos or not neg:
        return None
    # Mann-Whitney U statistic
    combined = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg], key=lambda t: t[0])
    rank_sum = 0.0
    i, n = 0, len(combined)
    while i < n:
        j = i
        while j < n and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for k in range(i, j):
            if combined[k][1] == 1:
                rank_sum += avg_rank
        i = j
    u = rank_sum - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


def _calibration_gap(fc: list[float], obs: list[float]) -> dict:
    """Mean-forecast minus mean-realized — the sign and size of the calibration
    offset. Negative ⇒ the system under-forecasts (misses peaks); positive ⇒ it
    cries wolf. This is the honest headline for trust: not a neat BSS sign but
    *where* the probability curve sits relative to what actually unfolds."""
    if not fc:
        return {"mean_forecast": 0.0, "mean_realized": 0.0, "gap": 0.0}
    mf, mo = float(np.mean(fc)), float(np.mean(obs))
    return {
        "mean_forecast": round(mf, 4),
        "mean_realized": round(mo, 4),
        "gap": round(mf - mo, 4),
        "sign": "under-forecast" if mf < mo else "over-forecast" if mf > mo else "calibrated",
    }


def _reliability(fc_scores: list[float], events: list[int]) -> list[dict]:
    """Reliability diagram — forecast deciles vs observed event fraction."""
    if not fc_scores:
        return []
    out = []
    for lo, hi in zip(RELIABILITY_BINS[:-1], RELIABILITY_BINS[1:]):
        idx = [i for i, f in enumerate(fc_scores) if lo <= f < hi]
        if not idx:
            continue
        obs_frac = float(np.mean([events[i] for i in idx]))
        out.append(
            {
                "band": f"{lo:.1f}–{hi:.1f}",
                "forecasts": len(idx),
                "mean_forecast": round(float(np.mean([fc_scores[i] for i in idx])), 3),
                "observed_fraction": round(obs_frac, 3),
            }
        )
    return out


def verify_zone(db, loc: Location) -> dict:
    """Rolling verification for a single zone — deterministic on its seed arc."""
    from app.hazards.registry import get_hazard

    hazard = get_hazard(loc.hazard_type)
    weather = [
        {
            "rainfall_mm": w.rainfall_mm,
            "humidity": w.humidity,
            "wind_kmh": w.wind_kmh,
            "rain_forecast_mm": w.rain_forecast_mm,
        }
        for w in db.query(WeatherSnapshot).filter_by(location_id=loc.id).order_by(WeatherSnapshot.captured_at).all()
    ]
    sat = [
        {"soil_moisture_anomaly": f.soil_moisture_anomaly}
        for f in db.query(SatelliteFrame).filter_by(location_id=loc.id).order_by(SatelliteFrame.captured_at).all()
    ]
    exposure, cap = _exposure(loc), loc.drainage_capacity_mmh

    fc_scores, realized, widths = [], [], []
    for t0 in STARTS:
        if t0 >= len(weather):
            continue
        comps_t0 = hour_components(hazard.id, weather, sat, t0, exposure, cap)
        feed = signal_from_weather(weather[: t0 + 1])
        for hz in HORIZONS:
            target = t0 + hz
            if target >= len(weather):
                continue
            lead_comps, _ = components_ahead(comps_t0, hazard.id, feed, exposure, hz)
            p_fc = min(1.0, max(0.0, float(hazard.probability(lead_comps))))
            p_obs = hazard.probability(hour_components(hazard.id, weather, sat, target, exposure, cap))
            fc_scores.append(p_fc)
            realized.append(p_obs)
            history = [hour_components(hazard.id, weather, sat, h, exposure, cap) for h in range(12, t0 + 1)]
            widths.append(
                _band_width(
                    DEFAULT_FORECASTER.fit_forecast(
                        [hazard.probability(c) for c in history], datetime.now(timezone.utc), hz
                    )
                )
            )
    if not fc_scores:
        return {"location_id": loc.id, "hazard": hazard.id, "samples": 0, "tier": "C"}

    fc_arr = np.asarray(fc_scores)
    obs_arr = np.asarray(realized)
    brier = float(np.mean((fc_arr - obs_arr) ** 2))
    climatology = float(np.mean(obs_arr))
    brier_clim = float(np.mean((climatology - obs_arr) ** 2))
    skill = 1.0 - brier / brier_clim if brier_clim > 1e-9 else 0.0
    high_cut = hazard.thresholds.get("high", 0.6)
    events = [1 if r >= high_cut else 0 for r in realized]
    auc = _auc(fc_scores, events)
    # Base-rate guard: on a near-degenerate window MSE-skill vs climatology is
    # meaningless; rank discrimination (AUC) rescues the grade there. Never
    # upgrade a zone that has neither.
    if brier_clim > 1e-3:
        tier = "A" if skill >= 0.30 else "B" if (skill >= 0.12 or (auc or 0.0) >= 0.72) else "C"
    else:
        tier = "A" if (auc or 0.0) >= 0.75 else "B" if (auc or 0.0) >= 0.62 else "C"
    return {
        "location_id": loc.id,
        "location_name": loc.name,
        "hazard": hazard.id,
        "samples": len(fc_scores),
        "brier": round(brier, 4),
        "brier_skill": round(skill, 4),
        "auc": auc,
        "climatology": round(climatology, 4),
        "calibration": _calibration_gap(fc_scores, obs_arr.tolist()),
        "band_tightness": round(float(np.mean(widths)) if widths else 0.0, 4),
        "tier": tier,
    }


def verify_scope(db, scope: str | None = None) -> dict:
    """Full verification pass for the live theatre. Cached per (scope, clock)."""
    key = _cache_key(db, scope)
    if key in _CACHE:
        return _CACHE[key]

    zones = db.query(Location).all()
    per_zone = [verify_zone(db, z) for z in zones]

    by_hazard: dict[str, dict] = {}
    for z in per_zone:
        agg = by_hazard.setdefault(
            z["hazard"],
            {
                "samples": 0,
                "brier_n": 0.0,
                "bss_n": 0.0,
                "zones": 0,
                "tiers": {"A": 0, "B": 0, "C": 0},
            },
        )
        agg["zones"] += 1
        agg["tiers"][z["tier"]] += 1
        if z["samples"]:
            agg["samples"] += z["samples"]
            agg["brier_n"] += z["brier"] * z["samples"]
            agg["bss_n"] += z["brier_skill"] * z["samples"]

    total_samples = sum(a["samples"] for a in by_hazard.values())
    overall_brier = sum(a["brier_n"] for a in by_hazard.values()) / total_samples if total_samples else 0.0
    overall_bss = sum(a["bss_n"] for a in by_hazard.values()) / total_samples if total_samples else 0.0

    # reliability/AUC need raw (forecast, realized) pairs — recompute pooled pairs
    pooled = _pooled_pairs(db, zones)

    result = {
        "scope": (db.query(Location).first().region if not scope and db.query(Location).first() else scope),
        "generated_at": datetime.now(timezone.utc),
        "method": "rolling holdout — lead-aware ladder at t0∈{12,24,36,48} scored at t0+{1,3,6,12,24} vs realized telemetry",
        "overall": {
            "brier": round(overall_brier, 4),
            "brier_skill": round(overall_bss, 4),
            "auc": _auc(pooled["fc"], pooled["events"]),
            "samples": total_samples,
            "zones": len(zones),
            "reliability": _reliability(pooled["fc"], pooled["events"]),
            "calibration": _calibration_gap(pooled["fc"], pooled["obs"]),
            "sharpness": round(
                float(np.mean([z["band_tightness"] for z in per_zone if z["band_tightness"]]) or 0.0), 4
            ),
        },
        "hazards": {
            hid: {
                "zones": a["zones"],
                "samples": a["samples"],
                "brier": round(a["brier_n"] / a["samples"], 4) if a["samples"] else None,
                "brier_skill": round(a["bss_n"] / a["samples"], 4) if a["samples"] else None,
                "tiers": a["tiers"],
            }
            for hid, a in sorted(by_hazard.items())
        },
        "zones": sorted(per_zone, key=lambda z: z["brier_skill"] if z["samples"] else -1),
    }
    _CACHE[key] = result
    return result


def _pooled_pairs(db, zones: list[Location]) -> dict:
    fc, obs, events = [], [], []
    for loc in zones:
        from app.hazards.registry import get_hazard

        hazard = get_hazard(loc.hazard_type)
        weather = [
            {
                "rainfall_mm": w.rainfall_mm,
                "humidity": w.humidity,
                "wind_kmh": w.wind_kmh,
                "rain_forecast_mm": w.rain_forecast_mm,
            }
            for w in db.query(WeatherSnapshot).filter_by(location_id=loc.id).order_by(WeatherSnapshot.captured_at).all()
        ]
        sat = [
            {"soil_moisture_anomaly": f.soil_moisture_anomaly}
            for f in db.query(SatelliteFrame).filter_by(location_id=loc.id).order_by(SatelliteFrame.captured_at).all()
        ]
        exposure, cap = _exposure(loc), loc.drainage_capacity_mmh
        for t0 in STARTS:
            if t0 >= len(weather):
                continue
            comps_t0 = hour_components(hazard.id, weather, sat, t0, exposure, cap)
            feed = signal_from_weather(weather[: t0 + 1])
            for hz in HORIZONS:
                target = t0 + hz
                if target >= len(weather):
                    continue
                lead_comps, _ = components_ahead(comps_t0, hazard.id, feed, exposure, hz)
                p_fc = min(1.0, max(0.0, float(hazard.probability(lead_comps))))
                p_obs = hazard.probability(hour_components(hazard.id, weather, sat, target, exposure, cap))
                fc.append(p_fc)
                obs.append(p_obs)
                events.append(1 if p_obs >= hazard.thresholds.get("high", 0.6) else 0)
    return {"fc": fc, "obs": obs, "events": events}


def zone_precision(db, loc: Location) -> dict:
    """Cached per-zone precision record for summaries/detail payloads."""
    res = verify_scope(db)
    for z in res["zones"]:
        if z["location_id"] == loc.id:
            return z
    return {"location_id": loc.id, "hazard": loc.hazard_type, "samples": 0, "tier": "C"}
