"""Tamil Nadu state-wide catalog — deterministic synthetic seed.

Extends the Chennai Flood Command pilot (15 zones) with one flood-command anchor
zone per district headquarters across all 38 districts. Everything stays
provenance-tagged is_synthetic=True — the *schema, geometry and telemetry shape*
are real; the observations are a labelled simulation for demo and calibration.

The storm is a NE-monsoon trough that tracks south→north along the coast with a
small per-district phase lag (longitude-weighted) so the state arc is spatially
coherent: coastal/low-lying districts peak first and hardest.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np

from app.data.seeds.generate_chennai import SOURCES, _rain_curve, _rolling
from app.data.seeds.generate_chennai import ZONES as CHENNAI_ZONES

SEED_VERSION = "tamilnadu-v1"

# (zone_id, district, HQ name, lat, lon, elevation_m, drainage_capacity_mmh, population)
# elevation/capacity/population are synthetic-but-plausible; coastal basins are low-lying.
DISTRICTS = [
    ("tn_chennai", "Chennai", "Chennai", 13.0827, 80.2707, 5.0, 4.5, 7_100_000),
    ("tn_chengalpattu", "Chengalpattu", "Chengalpattu", 13.0213, 80.0827, 36.0, 6.5, 4_100_000),
    ("tn_kanchipuram", "Kanchipuram", "Kanchipuram", 12.8342, 79.7036, 88.0, 7.0, 3_300_000),
    ("tn_thiruvallur", "Thiruvallur", "Thiruvallur", 13.1434, 79.9084, 38.0, 6.0, 3_700_000),
    ("tn_ranipet", "Ranipet", "Ranipet", 12.9253, 79.3763, 163.0, 7.5, 1_100_000),
    ("tn_vellore", "Vellore", "Vellore", 12.9165, 79.1325, 196.0, 7.0, 2_900_000),
    ("tn_tirupattur", "Tirupattur", "Tirupattur", 12.7951, 78.6355, 350.0, 8.0, 1_200_000),
    ("tn_tiruvannamalai", "Tiruvannamalai", "Tiruvannamalai", 12.2746, 79.0763, 78.0, 6.5, 2_700_000),
    ("tn_kallakurichi", "Kallakurichi", "Kallakurichi", 11.3327, 78.8569, 180.0, 7.5, 1_400_000),
    ("tn_villupuram", "Villupuram", "Villupuram", 11.9398, 79.5313, 78.0, 6.0, 3_600_000),
    ("tn_salem", "Salem", "Salem", 11.6693, 78.1407, 200.0, 8.0, 3_500_000),
    ("tn_namakkal", "Namakkal", "Namakkal", 11.2663, 78.1750, 218.0, 8.0, 1_400_000),
    ("tn_dharmapuri", "Dharmapuri", "Dharmapuri", 12.1025, 78.1596, 463.0, 8.5, 1_300_000),
    ("tn_krishnagiri", "Krishnagiri", "Krishnagiri", 12.5081, 78.2078, 466.0, 8.5, 1_900_000),
    ("tn_erode", "Erode", "Erode", 12.0233, 77.3721, 183.0, 8.0, 2_300_000),
    ("tn_tiruppur", "Tiruppur", "Tiruppur", 11.0576, 77.3411, 300.0, 8.0, 2_400_000),
    ("tn_coimbatore", "Coimbatore", "Coimbatore", 11.0168, 76.9558, 409.0, 8.0, 3_500_000),
    ("tn_nilgiris", "Nilgiris", "Ooty", 11.4102, 76.6950, 2240.0, 10.0, 800_000),
    ("tn_tirunelveli", "Tirunelveli", "Tirunelveli", 8.7879, 77.7280, 763.0, 7.5, 2_700_000),
    ("tn_thoothukudi", "Thoothukudi", "Thoothukudi", 8.8107, 78.1411, 23.0, 5.0, 1_300_000),
    ("tn_kanyakumari", "Kanyakumari", "Nagercoil", 8.1894, 77.5940, 27.0, 5.5, 1_400_000),
    ("tn_tenkasi", "Tenkasi", "Tenkasi", 8.9604, 77.3181, 400.0, 7.5, 1_000_000),
    ("tn_virudhunagar", "Virudhunagar", "Virudhunagar", 9.5877, 77.9517, 102.0, 6.5, 1_500_000),
    ("tn_sivaganga", "Sivaganga", "Sivaganga", 10.7456, 77.9448, 140.0, 7.0, 1_100_000),
    ("tn_madurai", "Madurai", "Madurai", 9.9252, 78.1198, 147.0, 6.5, 3_100_000),
    ("tn_theni", "Theni", "Theni", 9.3450, 77.0640, 599.0, 8.5, 1_000_000),
    ("tn_dindigul", "Dindigul", "Dindigul", 10.3552, 78.0101, 122.0, 7.0, 1_600_000),
    ("tn_ramanathapuram", "Ramanathapuram", "Ramanathapuram", 9.4348, 78.2656, 50.0, 6.0, 1_300_000),
    ("tn_pudukkottai", "Pudukkottai", "Pudukkottai", 10.3830, 78.8250, 110.0, 6.5, 1_600_000),
    ("tn_trichy", "Tiruchirappalli", "Trichy", 10.7905, 78.7047, 53.0, 6.0, 2_700_000),
    ("tn_nagapattinam", "Nagapattinam", "Nagapattinam", 10.7570, 79.7890, 0.5, 4.0, 900_000),
    ("tn_ariyalur", "Ariyalur", "Ariyalur", 10.8540, 78.3700, 100.0, 7.0, 800_000),
    ("tn_perambalur", "Perambalur", "Perambalur", 11.3020, 78.7680, 250.0, 8.0, 500_000),
    ("tn_cuddalore", "Cuddalore", "Cuddalore", 11.7544, 79.7510, 40.0, 5.5, 2_600_000),
    ("tn_mayiladuthurai", "Mayiladuthurai", "Mayiladuthurai", 11.1185, 79.6530, 12.0, 5.0, 1_000_000),
    ("tn_tiruvarur", "Tiruvarur", "Tiruvarur", 10.8930, 79.6540, 121.0, 6.5, 1_200_000),
    ("tn_thanjavur", "Thanjavur", "Thanjavur", 10.7870, 79.1378, 30.0, 5.5, 2_100_000),
    ("tn_karur", "Karur", "Karur", 10.9587, 78.0703, 120.0, 7.0, 900_000),
]


def _rain_curve_state(hours: int, phase: float, seed: int) -> np.ndarray:
    """NE-monsoon trough; phase shifts the peak so the storm tracks along the coast."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    burst = 46 * np.exp(-((t - (0.84 + phase * 0.06)) ** 2) / 0.02)
    background = 4.0 + 2.2 * np.sin(2 * np.pi * t * 2 + phase * 3)
    noise = rng.normal(0, 1.8, hours)
    return np.clip(burst + background + noise, 0, None)


def generate(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=72)
    hours = 72

    zones = []
    # Chennai pilot zones — anchored to the calibrated 2015 narrative
    for zid, name, lat, lon, elev, cap, pop in CHENNAI_ZONES:
        exposure = max(0.55, 1.5 - elev / 10.0)
        rain = _rain_curve(hours, seed=abs(hash(zid)) % 10**6)
        zone = _build_zone(zid, name, "Chennai", lat, lon, elev, cap, pop, exposure, rain, start, hours)
        zones.append(zone)

    # District HQ zones — flood-command anchors, coast-weighted
    for i, (zid, dist, hq, lat, lon, elev, cap, pop) in enumerate(DISTRICTS):
        exposure = max(0.5, min(1.15, 1.5 - elev / 220.0))
        coastal = lon > 79.4 or lat < 9.0  # Coromandel coast / south tip
        if coastal:
            exposure += 0.08
        exposure = min(1.2, exposure)
        phase = (lon - 76.6) / (80.3 - 76.6) * 0.7
        rain = _rain_curve_state(hours, phase, seed=i * 7 + 3)
        zone = _build_zone(zid, f"{dist} HQ — {hq}", dist, lat, lon, elev, cap, pop, exposure, rain, start, hours)
        zones.append(zone)

    return {
        "version": SEED_VERSION,
        "generated_at": now.isoformat(),
        "is_synthetic": True,
        "scope": "tamilnadu",
        "sources": SOURCES,
        "zones": zones,
    }


def _build_zone(zid, name, region, lat, lon, elev, cap, pop, exposure, rain, start, hours) -> dict:
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
            "tags": ["monsoon", "tamil-nadu", "advisory"],
            "warning_level": 2,
            "credibility": 0.8,
            "source_id": "news-eom",
        }
    ]
    water_level_m = np.minimum(1.0, 0.2 + _rolling(rain_local, 6) * 6 / 156.0 * exposure)
    return {
        "id": zid,
        "name": name,
        "region": region,
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


if __name__ == "__main__":
    data = generate()
    with open("app/data/seeds/tamilnadu_seed.json", "w") as f:
        json.dump(data, f, indent=1)
    print(
        f"wrote {len(data['zones'])} zones ({len(CHENNAI_ZONES)} chennai + {len(DISTRICTS)} district HQs) "
        f"to tamilnadu_seed.json"
    )
