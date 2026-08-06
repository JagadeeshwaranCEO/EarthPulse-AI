"""Chennai Flood Command — deterministic synthetic seed dataset.

Anchored to the 2015 Chennai flood narrative and real institutions (IMD rainfall,
CWPRS river levels, NASA GPM, civic reports). EVERY row is provenance-tagged
is_synthetic=True — honesty by default.

Feature design (rolling windows, not cumulative) so the demo escalates: risk
drivers grow through the storm ramp (hours ~50–70), peak near the end of the seed
window, then ease. The sim clock (app/services/ticker.py) drives the live arc.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np

SEED_VERSION = "chennai-v1"

ZONES = [
    ("adyar_1", "Adyar River — Nandambakkam", 13.001, 80.238, 7.0, 8.5, 610_000),
    ("adyar_2", "Adyar River — Saidapet", 13.022, 80.224, 9.0, 8.0, 540_000),
    ("cooum_1", "Cooum — Choolaimedu", 13.055, 80.228, 6.5, 7.5, 480_000),
    ("cooum_2", "Cooum — Egmore", 13.078, 80.250, 6.0, 7.0, 520_000),
    ("ott_1", "Otteri Nullah — Shenoy Nagar", 13.085, 80.225, 5.5, 6.5, 450_000),
    ("ott_2", "Otteri Nullah — Perambur", 13.102, 80.247, 5.0, 6.0, 470_000),
    ("velachery", "Velachery wetland buffer", 12.979, 80.227, 4.5, 5.5, 560_000),
    ("adyar_3", "Adyar River — Kotturpuram", 13.015, 80.242, 5.0, 6.0, 430_000),
    ("north_chennai", "North Chennai lowlands", 13.130, 80.250, 4.0, 5.0, 780_000),
    ("porur", "Porur lake drainage", 13.037, 80.158, 8.0, 7.5, 390_000),
    ("tambaram", "Tambaram basin", 12.925, 80.118, 10.0, 8.0, 350_000),
    ("t_nagar", "T.Nagar storm drains", 13.041, 80.234, 8.5, 8.5, 420_000),
    ("mylapore", "Mylapore coastal ward", 13.037, 80.268, 3.5, 4.5, 400_000),
    ("ambattur", "Ambattur industrial belt", 13.114, 80.155, 6.0, 6.0, 360_000),
    ("guindy", "Guindy low-lying stretches", 13.007, 80.220, 5.5, 6.5, 330_000),
]

SOURCES = [
    {
        "id": "imd-rain",
        "name": "IMD rain gauges (synthetic demo feed)",
        "kind": "weather",
        "url": "https://mausam.imd.gov.in/",
        "license": "public",
        "description": "Hourly rainfall accumulation (synthetic pilot feed)",
    },
    {
        "id": "cwprs-level",
        "name": "CWPRS river level telemetry (synthetic demo feed)",
        "kind": "weather",
        "url": "https://cwprs.gov.in/",
        "license": "public",
        "description": "Adyar/Cooum canal levels vs capacity (synthetic pilot feed)",
    },
    {
        "id": "gpm-nasa",
        "name": "NASA GPM precipitation + soil moisture proxy",
        "kind": "satellite",
        "url": "https://gpm.nasa.gov/",
        "license": "public",
        "description": "Satellite precipitation frames (synthetic pilot feed)",
    },
    {
        "id": "copernicus-swi",
        "name": "Copernicus SWI soil wetness anomaly",
        "kind": "satellite",
        "url": "https://land.copernicus.eu/",
        "license": "public",
        "description": "Surface soil moisture anomaly (synthetic pilot feed)",
    },
    {
        "id": "civic-reports",
        "name": "Civic waterlogging hotline (synthetic demo feed)",
        "kind": "citizen",
        "url": "",
        "license": "demo",
        "description": "Verified citizen reports (synthetic pilot feed)",
    },
    {
        "id": "news-eom",
        "name": "NDMA + civic alert stream (synthetic demo feed)",
        "kind": "news",
        "url": "https://ndma.gov.in/",
        "license": "public",
        "description": "Official warnings stream (synthetic pilot feed)",
    },
]


def _rain_curve(hours: int, seed: int = 42) -> np.ndarray:
    """NE-monsoon onset: long ramp → intense late burst → rapid easing.

    Peak sits near the end of the seed window (t≈0.88) so the sim clock demo
    escalates through it live.
    """
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    burst = 44 * np.exp(-((t - 0.88) ** 2) / 0.02)
    background = 4.5 + 2.5 * np.sin(2 * np.pi * t * 2 + 0.5)
    noise = rng.normal(0, 1.8, hours)
    return np.clip(burst + background + noise, 0, None)


def _rolling(a: np.ndarray, w: int) -> np.ndarray:
    """Windowed mean with left-padding (warmup = no early saturation)."""
    out = np.zeros_like(a)
    for i in range(len(a)):
        lo = max(0, i - w + 1)
        out[i] = np.mean(a[lo : i + 1])
    return out


def generate(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=72)
    hours = 72
    rain = _rain_curve(hours)

    zones = []
    for zid, name, lat, lon, elev, cap, pop in ZONES:
        exposure = max(0.55, 1.5 - elev / 10.0)
        rain_local = rain * (0.8 + 0.35 * exposure)

        soil_moisture = np.minimum(12.0, _rolling(rain_local, 6) * 6 / 30.0 * exposure)
        drainage_stress = np.minimum(12.0, np.maximum(0.0, (_rolling(rain_local, 6) * 6 / cap - 8.0) / 3.0 * exposure))
        citizen_pressure = np.minimum(8.0, np.maximum(0.0, (drainage_stress - 9.0) * 0.8))

        weather = [
            {
                "captured_at": (start + timedelta(hours=h)).isoformat(),
                "rainfall_mm": round(float(rain_local[h]), 2),
                "rain_forecast_mm": round(float(rain_local[min(hours - 1, h + 6)] * 0.92), 2),
                "humidity": round(float(np.clip(70 + rain_local[h] * 0.8, 55, 98)), 1),
                "wind_kmh": round(float(np.clip(13 + rain_local[h] * 0.35, 5, 45)), 1),
                "source_id": "imd-rain",
            }
            for h in range(hours)
        ]
        sat = [
            {
                "captured_at": (start + timedelta(hours=h)).isoformat(),
                "soil_moisture_anomaly": round(float(soil_moisture[h]), 3),
                "surface_water_index": round(float(np.clip(soil_moisture[h] / 9.0, 0, 1)), 3),
                "source_id": "gpm-nasa" if h % 2 == 0 else "copernicus-swi",
            }
            for h in range(0, hours, 2)
        ]
        citizen = [
            {
                "location_id": zid,
                "reported_at": (start + timedelta(hours=h)).isoformat(),
                "category": "waterlogging" if citizen_pressure[h] > 3 else "rain_heavy",
                "severity_hint": int(np.clip(citizen_pressure[h] / 2, 1, 4)),
                "text": f"Waterlogging reported near {name.split('—')[0].strip()} during heavy rain",
                "verified": bool(citizen_pressure[h] > 1.2),
                "source_id": "civic-reports",
            }
            for h in range(30, hours, 2)
            if citizen_pressure[h] > 0.8
        ]
        news = [
            {
                "captured_at": (start + timedelta(hours=56)).isoformat(),
                "tags": ["monsoon", "chennai", "advisory"],
                "warning_level": 2,
                "credibility": 0.8,
                "source_id": "news-eom",
            }
        ]
        water_level_m = np.minimum(1.0, 0.2 + _rolling(rain_local, 6) * 6 / 156.0 * exposure)
        zones.append(
            {
                "id": zid,
                "name": name,
                "lat": lat,
                "lon": lon,
                "elevation_m": elev,
                "drainage_capacity_mmh": cap,
                "population": pop,
                "exposure": round(float(exposure), 3),
                "weather": weather,
                "satellite": sat,
                "citizen": citizen,
                "news": news,
                "water": [
                    {
                        "captured_at": (start + timedelta(hours=h)).isoformat(),
                        "level_m": round(float(water_level_m[h]), 3),
                        "capacity_m": 1.0,
                        "inflow_m3s": round(float(np.clip(8 + _rolling(rain_local, 12)[h] * 0.9, 5, 60)), 1),
                        "source_id": "cwprs-level",
                    }
                    for h in range(hours)
                ],
            }
        )

    return {
        "version": SEED_VERSION,
        "generated_at": now.isoformat(),
        "is_synthetic": True,
        "sources": SOURCES,
        "zones": zones,
    }


if __name__ == "__main__":
    data = generate()
    with open("app/data/seeds/chennai_seed.json", "w") as f:
        json.dump(data, f, indent=1)
    print(f"wrote {len(data['zones'])} zones, {len(data['sources'])} sources to chennai_seed.json")
