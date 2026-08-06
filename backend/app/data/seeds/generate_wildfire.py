"""California wildfire command theatre — deterministic synthetic seed.

Five wildland-urban interface zones under a heat-dome red-flag event: dry fuels,
collapsing humidity, gusting offshore wind and a dying soil-moisture anomaly.
Arc is phase-shifted per zone so the theatre is spatially coherent (foothills
dry out first, coastal basins lag). Provenance-tagged is_synthetic=True.

Telemetry matches the canonical tables:
- weather: rainfall_mm / rain_forecast_mm / humidity / wind_kmh (noaa-firewx)
- satellite: soil_moisture_anomaly / surface_water_index (viiirs-thermal + gpm-nasa)
- citizen: smoke/ignition sightings (civic-reports)
- news: red-flag advisory (news-eom)
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np

SOURCES = [
    {
        "id": "noaa-firewx",
        "name": "NOAA Fire Weather Service",
        "kind": "weather",
        "url": "https://www.weather.gov/fire/",
        "license": "US Gov / public domain",
        "is_synthetic": True,
        "description": "Fire weather watch inputs — humidity, sustained wind, rainfall.",
    },
    {
        "id": "viiirs-thermal",
        "name": "VIIRS Thermal Anomaly",
        "kind": "satellite",
        "url": "https://firms.modaps.eosdis.nasa.gov/",
        "license": "NASA LANCE/FS",
        "is_synthetic": True,
        "description": "Thermal anomaly clusters and dryness proxies from the VIIRS sensor.",
    },
    {
        "id": "gpm-nasa",
        "name": "GPM/NASA Precipitation",
        "kind": "satellite",
        "url": "https://gpm.nasa.gov/",
        "license": "NASA Open",
        "is_synthetic": True,
        "description": "Soil moisture / surface water proxies from GPM retrieval.",
    },
    {
        "id": "civic-reports",
        "name": "Civic Hazard Reporter",
        "kind": "citizen",
        "url": "",
        "license": "Community-verified",
        "is_synthetic": True,
        "description": "Verified smoke and ignition sightings from populated foothills.",
    },
    {
        "id": "news-eom",
        "name": "EOM News Wire",
        "kind": "news",
        "url": "",
        "license": "Editorial",
        "is_synthetic": True,
        "description": "County red-flag warnings and evacuation advisory feed.",
    },
]

SEED_VERSION = "california-wildfire-v1"

# (zone_id, name, region, lat, lon, elevation_m, drainage_capacity_mmh, population, exposure)
# exposure = vegetation/fuel loading + interface density (1.0 baseline, 1.35 heavy WUI).
ZONES = [
    ("ca_santa_rosa", "Santa Rosa — WUI", "Sonoma County", 38.4405, -122.7140, 164.0, 6.0, 178_000, 1.35),
    ("ca_paradise", "Paradise Ridge", "Butte County", 39.7596, -121.6219, 540.0, 6.5, 26_000, 1.40),
    ("ca_mariposa", "Mariposa Foothills", "Mariposa County", 37.4849, -119.9663, 670.0, 6.5, 1_800, 1.45),
    ("ca_la_basin", "Los Angeles Basin Rim", "Los Angeles County", 34.2032, -118.2216, 300.0, 6.0, 1_900_000, 1.25),
    ("ca_sd_backcountry", "San Diego Backcountry", "San Diego County", 33.0138, -116.7704, 620.0, 6.5, 640_000, 1.30),
]


def _arc(hours: int, phase: float, seed: int) -> dict[str, np.ndarray]:
    """Heat-dome: humidity collapses, wind ramps and peaks, rain stays near zero."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    humidity = 55 - 34 * np.clip((t + phase * 0.05) * 1.15, 0, 1) + rng.normal(0, 2, hours)
    wind = 14 + 34 * np.clip((t - 0.15 + phase * 0.06) / 0.7, 0, 1) - 6 * np.clip((t - 0.85) / 0.15, 0, 1)
    rain = np.clip(1.0 + 0.8 * np.sin(2 * np.pi * t * 3 + phase * 2) + rng.normal(0, 0.4, hours), 0, 2.5)
    soil = 4.2 - 3.7 * np.clip((t + phase * 0.06) * 1.1, 0, 1) + rng.normal(0, 0.15, hours)
    return {
        "humidity": np.clip(humidity, 12, 70),
        "wind_kmh": np.clip(wind, 4, 55),
        "rainfall_mm": rain,
        "soil_anomaly": np.clip(soil, 0.1, 6.0),
    }


def generate(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=72)
    hours = 72

    zones = []
    for i, (zid, name, region, lat, lon, elev, cap, pop, exposure) in enumerate(ZONES):
        arc = _arc(hours, phase=(i % 3) * 0.06, seed=i * 11 + 5)
        zones.append(_build_zone(zid, name, region, lat, lon, elev, cap, pop, exposure, arc, start, hours))

    return {
        "version": SEED_VERSION,
        "generated_at": now.isoformat(),
        "is_synthetic": True,
        "scope": "wildfire",
        "sources": SOURCES,
        "zones": zones,
    }


def _build_zone(zid, name, region, lat, lon, elev, cap, pop, exposure, arc, start, hours) -> dict:
    h = arc["humidity"]
    w = arc["wind_kmh"]
    r = arc["rainfall_mm"]
    soil = arc["soil_anomaly"]
    swi = np.clip(soil / 9.0, 0.03, 0.6)

    weather = [
        {
            "captured_at": (start + timedelta(hours=t)).isoformat(),
            "rainfall_mm": round(float(r[t]), 2),
            "rain_forecast_mm": round(float(r[min(hours - 1, t + 6)] * 0.95), 2),
            "humidity": round(float(h[t]), 1),
            "wind_kmh": round(float(w[t]), 1),
            "source_id": "noaa-firewx",
        }
        for t in range(hours)
    ]
    sat = [
        {
            "captured_at": (start + timedelta(hours=t)).isoformat(),
            "soil_moisture_anomaly": round(float(soil[t]), 3),
            "surface_water_index": round(float(swi[t]), 3),
            "source_id": "viiirs-thermal" if t % 3 == 0 else "gpm-nasa",
        }
        for t in range(0, hours, 2)
    ]
    dry_pressure = np.clip((60.0 - h) * exposure, 0, 50.0)
    citizen = [
        {
            "location_id": zid,
            "reported_at": (start + timedelta(hours=t)).isoformat(),
            "category": "flame_sighting" if dry_pressure[t] > 34 else "smoke_sighting",
            "severity_hint": int(np.clip(dry_pressure[t] / 14.0, 1, 5)),
            "text": f"Smoke column reported near {name} foothills; ember cast on ridgeline wind",
            "verified": bool(dry_pressure[t] > 26),
            "source_id": "civic-reports",
        }
        for t in range(36, hours, 3)
        if dry_pressure[t] > 22
    ]
    news = [
        {
            "captured_at": (start + timedelta(hours=58)).isoformat(),
            "tags": ["wildfire", "california", "red-flag"],
            "warning_level": 3,
            "credibility": 0.9,
            "source_id": "news-eom",
        }
    ]
    return {
        "id": zid,
        "name": name,
        "region": region,
        "lat": lat,
        "lon": lon,
        "elevation_m": elev,
        "drainage_capacity_mmh": cap,
        "population": pop,
        "hazard_type": "wildfire",
        "exposure": round(float(exposure), 3),
        "weather": weather,
        "satellite": sat,
        "citizen": citizen,
        "news": news,
    }


if __name__ == "__main__":
    data = generate()
    with open("app/data/seeds/wildfire_seed.json", "w") as f:
        json.dump(data, f, indent=1)
    n_cit = sum(len(z["citizen"]) for z in data["zones"])
    print(f"wrote {len(data['zones'])} zones to wildfire_seed.json ({n_cit} citizen sightings)")
