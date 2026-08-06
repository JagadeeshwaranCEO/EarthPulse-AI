"""All-India command theatre — deterministic synthetic seed.

Covers every state and union territory with state/UT capital anchors plus
hazard hotspots, hazard-typed per regional climatology:

- cyclone — Bay of Bengal / Arabian Sea coastal districts (surge + wind field)
- wildfire — forest / dry-deciduous districts (fuel dryness + wind)
- flood — Ganges basin, Brahmaputra valley, monsoon coastal (rain burst)

The event is a monsoon-plus event: a cyclonic disturbance tracks the Bay of
Bengal coast with a rain band that reaches inland flood districts, while dry
foothill districts stay under heat-dome fuel-dryness pressure. Every zone's
telemetry is deterministic and provenance-tagged is_synthetic=True; the schema,
geometry and hazard typing are real.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np

SOURCES = [
    {
        "id": "imd-rain",
        "name": "IMD Rain Gauge Network",
        "kind": "weather",
        "url": "https://mausam.imd.gov.in/",
        "license": "IMD / Indian Govt",
        "is_synthetic": True,
        "description": "Rainfall and forecast series from IMD gauge network.",
    },
    {
        "id": "imd-cyclone",
        "name": "IMD Cyclone Warning Division",
        "kind": "weather",
        "url": "https://rsmcnewdelhi.imd.gov.in/",
        "license": "IMD / Indian Govt",
        "is_synthetic": True,
        "description": "Cyclone track cones, wind field and surge advisories.",
    },
    {
        "id": "noaa-firewx",
        "name": "NOAA Fire Weather Service",
        "kind": "weather",
        "url": "https://www.weather.gov/fire/",
        "license": "US Gov / public domain",
        "is_synthetic": True,
        "description": "Humidity, sustained wind and rainfall for dryness telemetry.",
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
        "id": "viiirs-thermal",
        "name": "VIIRS Thermal Anomaly",
        "kind": "satellite",
        "url": "https://firms.modaps.eosdis.nasa.gov/",
        "license": "NASA LANCE/FS",
        "is_synthetic": True,
        "description": "Thermal anomaly clusters and dryness proxies from the VIIRS sensor.",
    },
    {
        "id": "civic-reports",
        "name": "Civic Hazard Reporter",
        "kind": "citizen",
        "url": "",
        "license": "Community-verified",
        "is_synthetic": True,
        "description": "Verified sightings — inundation, smoke, sea-state rise.",
    },
    {
        "id": "news-eom",
        "name": "EOM News Wire",
        "kind": "news",
        "url": "",
        "license": "Editorial",
        "is_synthetic": True,
        "description": "State advisories — monsoon, red-flag and cyclone warnings.",
    },
]

SEED_VERSION = "india-all-states-v1"

# (zone_id, name, region, lat, lon, elevation_m, drainage_capacity_mmh, population, hazard, exposure)
# exposure: 1.0 baseline; coastal surge blocks 1.2-1.45; hill forests 1.2-1.4.
CAPITALS = [
    ("in_an_ammu", "Amaravati (Andhra)", "Andhra Pradesh", 16.5062, 80.6480, 20.0, 5.5, 5_200_000, "cyclone", 1.3),
    ("in_ar_itn", "Itanagar (Arunachal)", "Arunachal Pradesh", 27.0844, 93.6053, 320.0, 7.0, 85_000, "flood", 0.9),
    ("in_as_gsu", "Guwahati (Assam)", "Assam", 26.1445, 91.7362, 55.0, 5.0, 1_100_000, "flood", 1.2),
    ("in_br_pat", "Patna (Bihar)", "Bihar", 25.5941, 85.1376, 53.0, 5.0, 2_100_000, "flood", 1.25),
    ("in_cg_raipur", "Raipur (Chhattisgarh)", "Chhattisgarh", 21.2514, 81.6296, 298.0, 6.5, 1_100_000, "flood", 1.0),
    ("in_ga_pnj", "Panaji (Goa)", "Goa", 15.4909, 73.8278, 7.0, 5.5, 115_000, "cyclone", 1.35),
    ("in_gj_gnd", "Gandhinagar (Gujarat)", "Gujarat", 23.2156, 72.6369, 81.0, 6.0, 2_100_000, "flood", 0.9),
    ("in_hr_cdg", "Chandigarh (Haryana)", "Haryana", 30.7333, 76.7794, 321.0, 6.5, 1_100_000, "flood", 0.8),
    ("in_hp_shimla", "Shimla (Himachal)", "Himachal Pradesh", 31.1048, 77.1734, 2276.0, 8.0, 170_000, "wildfire", 1.2),
    ("in_jk_sgr", "Srinagar (J&K)", "Jammu & Kashmir", 34.0837, 74.7973, 1585.0, 7.5, 1_200_000, "flood", 1.1),
    ("in_jh_ran", "Ranchi (Jharkhand)", "Jharkhand", 23.3441, 85.3096, 651.0, 7.0, 1_200_000, "wildfire", 1.2),
    ("in_ka_bgl", "Bengaluru (Karnataka)", "Karnataka", 12.9716, 77.5946, 920.0, 7.0, 12_300_000, "flood", 0.8),
    ("in_kl_trv", "Thiruvananthapuram (Kerala)", "Kerala", 8.5241, 76.9366, 10.0, 5.0, 960_000, "cyclone", 1.3),
    ("in_mp_bpl", "Bhopal (Madhya Pradesh)", "Madhya Pradesh", 23.2599, 77.4126, 527.0, 6.5, 2_400_000, "flood", 0.8),
    ("in_mh_bom", "Mumbai (Maharashtra)", "Maharashtra", 19.0760, 72.8777, 14.0, 4.5, 20_700_000, "flood", 1.35),
    ("in_mn_imph", "Imphal (Manipur)", "Manipur", 24.8170, 93.9368, 786.0, 6.5, 270_000, "flood", 0.9),
    ("in_ml_shl", "Shillong (Meghalaya)", "Meghalaya", 25.5788, 91.8933, 1525.0, 7.0, 140_000, "flood", 1.0),
    ("in_mz_aiz", "Aizawl (Mizoram)", "Mizoram", 23.7271, 92.7176, 1132.0, 7.0, 290_000, "flood", 0.9),
    ("in_nl_koh", "Kohima (Nagaland)", "Nagaland", 25.6751, 94.1086, 1444.0, 7.0, 100_000, "wildfire", 1.2),
    ("in_or_bbs", "Bhubaneswar (Odisha)", "Odisha", 20.2961, 85.8245, 45.0, 5.0, 880_000, "cyclone", 1.3),
    ("in_pb_lud", "Ludhiana (Punjab)", "Punjab", 30.9010, 75.8573, 262.0, 6.5, 1_600_000, "flood", 1.0),
    ("in_rj_jpr", "Jaipur (Rajasthan)", "Rajasthan", 26.9124, 75.7873, 431.0, 7.0, 3_100_000, "flood", 0.8),
    ("in_sk_gng", "Gangtok (Sikkim)", "Sikkim", 27.3389, 88.6065, 1436.0, 7.0, 100_000, "flood", 0.9),
    ("in_tn_chennai", "Chennai (Tamil Nadu)", "Tamil Nadu", 13.0827, 80.2707, 5.0, 4.5, 7_100_000, "cyclone", 1.4),
    ("in_tg_hyd", "Hyderabad (Telangana)", "Telangana", 17.3850, 78.4867, 505.0, 6.5, 10_500_000, "flood", 0.9),
    ("in_tr_agr", "Agartala (Tripura)", "Tripura", 23.8315, 91.2868, 12.8, 5.5, 400_000, "flood", 1.0),
    ("in_up_lko", "Lucknow (Uttar Pradesh)", "Uttar Pradesh", 26.8467, 80.9462, 123.0, 5.5, 3_200_000, "flood", 1.1),
    ("in_uk_deh", "Dehradun (Uttarakhand)", "Uttarakhand", 30.3165, 78.0322, 450.0, 6.5, 570_000, "wildfire", 1.3),
    ("in_wb_kol", "Kolkata (West Bengal)", "West Bengal", 22.5726, 88.3639, 6.0, 4.5, 14_900_000, "cyclone", 1.4),
]

UTS = [
    ("in_an_pbl", "Port Blair (A&N)", "Andaman & Nicobar", 11.6234, 92.7265, 16.0, 6.0, 100_000, "cyclone", 1.4),
    ("in_ch_chd", "Chandigarh (UT)", "Chandigarh", 30.7333, 76.7794, 321.0, 6.5, 1_100_000, "flood", 0.8),
    (
        "in_dn_dm",
        "Daman (D&NH+DD)",
        "Dadra & Nagar Haveli / Daman & Diu",
        20.3974,
        72.8328,
        5.0,
        5.5,
        115_000,
        "cyclone",
        1.3,
    ),
    ("in_dl_nd", "New Delhi (NCT)", "Delhi", 28.6139, 77.2090, 216.0, 5.0, 16_800_000, "flood", 1.15),
    ("in_ld_kav", "Kavaratti (Lakshadweep)", "Lakshadweep", 10.5593, 72.6358, 2.0, 5.0, 11_000, "cyclone", 1.5),
    ("in_py_pdc", "Puducherry (UT)", "Puducherry", 11.9416, 79.8083, 3.0, 5.0, 950_000, "cyclone", 1.4),
    ("in_lk_lch", "Leh (Ladakh)", "Ladakh", 34.1526, 77.5771, 3500.0, 8.0, 30_000, "flood", 0.8),
    ("in_jk_jmu", "Jammu (J&K UT)", "Jammu & Kashmir", 32.7266, 74.8570, 327.0, 6.5, 1_400_000, "flood", 1.0),
]

# Hazard hotspots beyond capitals — 2-3 per big state + key river/forest/coast districts
HOTSPOTS = [
    # Bay of Bengal cyclone belt
    ("in_od_puri", "Puri Coast", "Odisha", 19.8135, 85.8312, 8.0, 4.5, 200_000, "cyclone", 1.45),
    ("in_od_bal", "Balasore Coast", "Odisha", 21.4936, 86.9339, 6.0, 4.5, 400_000, "cyclone", 1.4),
    ("in_ap_kak", "Kakinada Coast", "Andhra Pradesh", 16.9891, 82.2475, 3.0, 4.5, 440_000, "cyclone", 1.45),
    ("in_ap_vis", "Visakhapatnam Port", "Andhra Pradesh", 17.6868, 83.2185, 5.0, 5.0, 2_100_000, "cyclone", 1.4),
    ("in_tn_nagapattinam", "Nagapattinam Coast", "Tamil Nadu", 10.7570, 79.7890, 0.5, 4.0, 900_000, "cyclone", 1.5),
    ("in_tn_ram", "Rameswaram Strait", "Tamil Nadu", 9.2876, 79.3129, 1.0, 4.5, 60_000, "cyclone", 1.5),
    ("in_wb_s24", "Sundarbans South", "West Bengal", 21.9497, 88.9156, 2.0, 4.0, 1_600_000, "cyclone", 1.55),
    ("in_wb_mid", "Midnapore Coastal", "West Bengal", 22.2547, 87.6536, 6.0, 4.5, 1_900_000, "cyclone", 1.4),
    # Arabian Sea belt
    ("in_gj_kut", "Kutch Coast", "Gujarat", 23.1536, 69.2670, 8.0, 5.5, 200_000, "cyclone", 1.35),
    ("in_gj_surat", "Surat Estuary", "Gujarat", 21.1702, 72.8311, 13.0, 5.0, 6_500_000, "cyclone", 1.3),
    ("in_mh_raigad", "Raigad Coast", "Maharashtra", 18.9087, 72.9787, 11.0, 5.0, 2_600_000, "cyclone", 1.3),
    ("in_kl_alp", "Alappuzha Backwaters", "Kerala", 9.4981, 76.3388, 3.0, 4.5, 2_100_000, "cyclone", 1.45),
    ("in_ka_kar", "Karwar Coast", "Karnataka", 14.8136, 74.1297, 6.0, 5.5, 180_000, "cyclone", 1.3),
    # Ganges / Brahmaputra floodplain
    ("in_up_prg", "Prayagraj Confluence", "Uttar Pradesh", 25.4358, 81.8463, 98.0, 5.0, 1_200_000, "flood", 1.3),
    ("in_up_var", "Varanasi Ghats", "Uttar Pradesh", 25.3176, 82.9739, 80.0, 5.0, 1_400_000, "flood", 1.25),
    ("in_br_bhag", "Bhagalpur Reach", "Bihar", 25.2445, 86.9718, 43.0, 4.5, 400_000, "flood", 1.4),
    ("in_br_darb", "Darbhanga Basin", "Bihar", 26.1542, 85.8918, 48.0, 4.5, 300_000, "flood", 1.45),
    ("in_as_kaz", "Kaziranga Corridor", "Assam", 26.5775, 93.1711, 80.0, 4.5, 60_000, "flood", 1.5),
    ("in_as_dhbr", "Dhubri Brahmputra", "Assam", 26.0225, 89.9797, 30.0, 4.5, 150_000, "flood", 1.45),
    ("in_wb_hooghly", "Hooghly Industrial", "West Bengal", 22.8964, 88.3792, 8.0, 4.5, 5_800_000, "flood", 1.3),
    ("in_dl_yam", "Delhi Yamuna Belt", "Delhi", 28.6500, 77.2300, 205.0, 4.8, 3_500_000, "flood", 1.25),
    ("in_mh_mum", "Mumbai Central Basin", "Maharashtra", 19.0330, 72.8560, 8.0, 4.0, 9_500_000, "flood", 1.45),
    ("in_ka_bgl2", "Bengaluru East", "Karnataka", 12.9716, 77.7500, 910.0, 6.0, 4_200_000, "flood", 1.0),
    ("in_rj_bharat", "Bharatpur Wetlands", "Rajasthan", 27.2173, 77.4901, 183.0, 6.0, 250_000, "flood", 1.2),
    ("in_mp_gwa", "Gwalior Chambal", "Madhya Pradesh", 26.2183, 78.1828, 196.0, 6.0, 1_100_000, "flood", 1.1),
    ("in_jh_sah", "Sahibganj Ganga", "Jharkhand", 25.2379, 87.6591, 26.0, 5.0, 150_000, "flood", 1.3),
    ("in_cg_bil", "Bilaspur Mahanadi", "Chhattisgarh", 22.0797, 82.1399, 262.0, 6.0, 430_000, "flood", 1.0),
    ("in_pb_fzr", "Ferozepur Sutlej", "Punjab", 30.9330, 74.6130, 199.0, 6.0, 110_000, "flood", 1.25),
    ("in_sk_mgn", "Rangpo Tista", "Sikkim", 27.1773, 88.5435, 450.0, 6.0, 30_000, "flood", 1.25),
    # Wildfire / dry deciduous belt
    ("in_uk_nain", "Nainital Ridge", "Uttarakhand", 29.3919, 79.4542, 2084.0, 8.0, 50_000, "wildfire", 1.4),
    ("in_uk_har", "Haridwar Forest", "Uttarakhand", 29.9466, 78.1609, 314.0, 6.5, 310_000, "wildfire", 1.3),
    ("in_hp_kangra", "Kangra Valley", "Himachal Pradesh", 32.1000, 76.2690, 733.0, 7.0, 300_000, "wildfire", 1.3),
    ("in_or_sund", "Sundargarh Forests", "Odisha", 22.1092, 84.0330, 233.0, 6.5, 250_000, "wildfire", 1.35),
    ("in_jh_haz", "Hazaribagh Palamu", "Jharkhand", 23.9925, 85.3620, 604.0, 7.0, 150_000, "wildfire", 1.35),
    ("in_cg_dant", "Dantewada Bastar", "Chhattisgarh", 18.9970, 81.3449, 350.0, 6.5, 130_000, "wildfire", 1.4),
    ("in_mp_bal", "Balaghat Sal", "Madhya Pradesh", 21.8157, 80.1886, 288.0, 6.5, 85_000, "wildfire", 1.3),
    ("in_ka_chik", "Chikkamagaluru Ghats", "Karnataka", 13.3161, 75.7720, 1030.0, 7.0, 110_000, "wildfire", 1.3),
    ("in_kl_way", "Wayanad Plateau", "Kerala", 11.6854, 76.1320, 700.0, 6.5, 85_000, "wildfire", 1.35),
    ("in_mh_gad", "Gadchiroli Forests", "Maharashtra", 20.1780, 80.0077, 213.0, 6.5, 110_000, "wildfire", 1.35),
    ("in_tg_war", "Warangal Deccan", "Telangana", 17.9689, 79.5941, 253.0, 6.5, 700_000, "wildfire", 1.2),
    ("in_ap_cud", "Cuddapah Scrub", "Andhra Pradesh", 14.4670, 78.8240, 138.0, 6.5, 340_000, "wildfire", 1.25),
    ("in_tn_wg", "Nilgiri Shola", "Tamil Nadu", 11.4102, 76.6950, 2240.0, 7.0, 90_000, "wildfire", 1.3),
    ("in_nl_mok", "Mokokchung Hills", "Nagaland", 26.3240, 94.5280, 1325.0, 7.0, 40_000, "wildfire", 1.3),
]

ALL_ZONES = CAPITALS + UTS + HOTSPOTS


def _flood_arc(hours: int, phase: float, seed: int, peak_mm: float) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    burst = peak_mm * np.exp(-((t - (0.78 + phase * 0.06)) ** 2) / 0.02)
    background = 3.0 + 2.0 * np.sin(2 * np.pi * t * 2 + phase * 3)
    noise = rng.normal(0, 1.5, hours)
    rain = np.clip(burst + background + noise, 0, None)
    humidity = np.clip(68 + rain * 0.7, 50, 98)
    wind = np.clip(13 + rain * 0.3, 5, 45)
    soil = np.clip(4.0 + rain * 0.28, 0.5, 12.0)
    return {"rainfall_mm": rain, "humidity": humidity, "wind_kmh": wind, "soil_anomaly": soil}


def _cyclone_arc(hours: int, phase: float, seed: int, intensity: float = 1.0) -> dict[str, np.ndarray]:
    """Bay of Bengal landfall: wind spirals up to storm strength, rain bands close in."""
    t = np.linspace(0, 1, hours)
    ramp = np.clip((t - 0.42 + phase * 0.04) / 0.38, 0, 1) - 0.2 * np.clip((t - 0.96) / 0.04, 0, 1)
    wind = np.clip((14 + 46 * ramp) * intensity, 4, 95)
    rain = 2 + 34 * np.clip((t - 0.5 + phase * 0.04) / 0.4, 0, 1) * np.exp(-((t - 0.9) ** 2) / 0.01) * intensity
    humidity = np.clip(62 + rain * 0.8, 55, 99)
    soil = np.clip(6.0 + rain * 0.3, 2.0, 12.0)
    return {"rainfall_mm": rain, "humidity": humidity, "wind_kmh": wind, "soil_anomaly": soil}


def _wildfire_arc(hours: int, phase: float, seed: int) -> dict[str, np.ndarray]:
    """Dry-deciduous heat: humidity collapses, wind ramps, rain near zero."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    humidity = 52 - 30 * np.clip((t + phase * 0.05) * 1.15, 0, 1) + rng.normal(0, 2, hours)
    wind = 12 + 32 * np.clip((t - 0.15 + phase * 0.06) / 0.7, 0, 1) - 5 * np.clip((t - 0.85) / 0.15, 0, 1)
    rain = np.clip(0.8 + 0.6 * np.sin(2 * np.pi * t * 3 + phase * 2) + rng.normal(0, 0.3, hours), 0, 2)
    soil = np.clip(3.6 - 3.1 * np.clip((t + phase * 0.06) * 1.1, 0, 1) + rng.normal(0, 0.15, hours), 0.2, 5.0)
    return {
        "rainfall_mm": rain,
        "humidity": np.clip(humidity, 15, 68),
        "wind_kmh": np.clip(wind, 4, 50),
        "soil_anomaly": soil,
    }


def generate(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=72)
    hours = 72

    zones = []
    for i, (zid, name, region, lat, lon, elev, cap, pop, hazard, exposure) in enumerate(ALL_ZONES):
        phase = (i % 5) * 0.07
        if hazard == "flood":
            peak = 55.0 if region in ("Assam", "Bihar") or "Puri" in name else 40.0
            arc = _flood_arc(hours, phase=phase, seed=i * 13 + 7, peak_mm=peak)
        elif hazard == "cyclone":
            # track proximity: zones closer to the track landfall carry a stronger wind field
            intensity = 0.75 + 0.42 * exposure
            arc = _cyclone_arc(hours, phase=phase, seed=i * 13 + 7, intensity=intensity)
        else:
            arc = _wildfire_arc(hours, phase=phase, seed=i * 13 + 7)
        zones.append(_build_zone(zid, name, region, lat, lon, elev, cap, pop, hazard, exposure, arc, start, hours))

    return {
        "version": SEED_VERSION,
        "generated_at": now.isoformat(),
        "is_synthetic": True,
        "scope": "india",
        "sources": SOURCES,
        "zones": zones,
    }


def _rolling(x: np.ndarray, w: int) -> np.ndarray:
    kernel = np.ones(w) / w
    return np.convolve(x, kernel, mode="same")


def _build_zone(zid, name, region, lat, lon, elev, cap, pop, hazard, exposure, arc, start, hours) -> dict:
    rain = arc["rainfall_mm"]
    humidity = arc["humidity"]
    wind = arc["wind_kmh"]
    soil = arc["soil_anomaly"]

    if hazard == "flood":
        sat = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "soil_moisture_anomaly": round(float(soil[t]), 3),
                "surface_water_index": round(float(np.clip(soil[t] / 9.0, 0, 1)), 3),
                "source_id": "gpm-nasa" if t % 2 == 0 else "viiirs-thermal",
            }
            for t in range(0, hours, 2)
        ]
        water = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "level_m": round(float(np.minimum(1.0, 0.2 + _rolling(rain, 6)[t] * 6 / 156.0 * exposure)), 3),
                "capacity_m": 1.0,
                "inflow_m3s": round(float(np.clip(8 + _rolling(rain, 12)[t] * 0.9, 5, 60)), 1),
                "source_id": "cwprs-level",
            }
            for t in range(hours)
        ]
    else:
        sat = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "soil_moisture_anomaly": round(float(soil[t]), 3),
                "surface_water_index": round(float(np.clip(soil[t] / 9.0, 0.02, 0.6)), 3),
                "source_id": "viiirs-thermal" if t % 3 == 0 else "gpm-nasa",
            }
            for t in range(0, hours, 2)
        ]
        water = []

    citizen = _citizen_reports(zid, name, hazard, humidity, wind, rain, start, hours, exposure)

    weather = [
        {
            "captured_at": (start + timedelta(hours=t)).isoformat(),
            "rainfall_mm": round(float(rain[t]), 2),
            "rain_forecast_mm": round(float(rain[min(hours - 1, t + 6)] * 0.94), 2),
            "humidity": round(float(humidity[t]), 1),
            "wind_kmh": round(float(wind[t]), 1),
            "source_id": "imd-cyclone"
            if hazard == "cyclone"
            else ("noaa-firewx" if hazard == "wildfire" else "imd-rain"),
        }
        for t in range(hours)
    ]
    news = [
        {
            "captured_at": (start + timedelta(hours=58)).isoformat(),
            "tags": {
                "flood": ["monsoon", "india", "advisory"],
                "cyclone": ["cyclone", "india", "landfall"],
                "wildfire": ["wildfire", "india", "red-flag"],
            }[hazard],
            "warning_level": 3 if hazard == "cyclone" else 2,
            "credibility": 0.85,
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
        "hazard_type": hazard,
        "exposure": round(float(exposure), 3),
        "weather": weather,
        "satellite": sat,
        "citizen": citizen,
        "news": news,
        "water": water,
    }


def _citizen_reports(zid, name, hazard, humidity, wind, rain, start, hours, exposure=1.0) -> list[dict]:
    out = []
    for t in range(36, hours, 3):
        if hazard == "flood":
            pressure = np.clip((_rolling(rain, 6)[t] * 6 / 22.0) - 6.0, 0, 8)
            if pressure <= 0.8:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "waterlogging",
                    "severity_hint": int(np.clip(pressure / 2, 1, 4)),
                    "text": f"Waterlogging reported near {name} during monsoon surge",
                    "verified": bool(pressure > 1.5),
                    "source_id": "civic-reports",
                }
            )
        elif hazard == "cyclone":
            pressure = np.clip((wind[t] - 30) / 8.0, 0, 8)
            if pressure <= 0.8:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "sea_state" if pressure > 4 else "wind_damage",
                    "severity_hint": int(np.clip(pressure / 1.6, 1, 5)),
                    "text": f"Sea-state rise and gust damage reported near {name} coast",
                    "verified": bool(pressure > 2),
                    "source_id": "civic-reports",
                }
            )
        else:
            dry_pressure = np.clip((60.0 - humidity[t]) * exposure, 0, 50)
            if dry_pressure <= 22:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "flame_sighting" if dry_pressure > 34 else "smoke_sighting",
                    "severity_hint": int(np.clip(dry_pressure / 14.0, 1, 5)),
                    "text": f"Smoke column reported near {name} forest fringe",
                    "verified": bool(dry_pressure > 26),
                    "source_id": "civic-reports",
                }
            )
    return out


if __name__ == "__main__":
    data = generate()
    with open("app/data/seeds/india_seed.json", "w") as f:
        json.dump(data, f, indent=1)
    counts = {}
    for z in data["zones"]:
        counts[z["hazard_type"]] = counts.get(z["hazard_type"], 0) + 1
    print(f"wrote {len(data['zones'])} zones to india_seed.json: {counts}")
