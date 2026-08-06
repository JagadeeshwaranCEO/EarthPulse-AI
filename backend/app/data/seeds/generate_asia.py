"""All-Asia command theatre — deterministic synthetic seed.

Nine hazards across ~110 zones covering the tectonic and climate belts of Asia:

- earthquake — Ring of Fire + Alpine-Himalayan belt metros (seismic episode telemetry)
- tsunami — tsunamigenic coasts: Bay of Bengal, Andaman, Pacific arcs
- volcanic — Merapi/Sinabung/Agung, Mayon/Taal/Pinatubo, Sakurajima, Kamchatka
- landslide — Himalayan + monsoon hill slopes (saturation + burst trigger)
- drought — central-Iran plateau, Sindh dry belt, Indochina monsoon-break dry zones
- heatwave — MENA Gulf domes, Indo-Gangetic hot corridor, east-Asia urban heat
- flood — Ganges-Brahmaputra delta, Chao Phraya, Pearl/Red River, Mekong basins
- cyclone — Philippine typhoon alley, South China Sea, Bay of Bengal landfall belt
- wildfire — Indonesian peat-haze belt, Chiang Mai smog bowl, Siberian taiga

Seismic/volcanic telemetry flows through the IngestedDatum archive (ground_accel,
seismic_energy, volcanic_tremor, so2_flux, ash_plume_km) so the canonical weather
tables stay untouched. Every zone is deterministic and is_synthetic=True.
"""

import json
from datetime import datetime, timedelta, timezone

import numpy as np

from app.data.seeds.generate_india import _cyclone_arc, _flood_arc, _wildfire_arc

SOURCES = [
    {
        "id": "wmo-gts",
        "name": "WMO GTS Meteorological Network",
        "kind": "weather",
        "url": "https://www.wmo.int/",
        "license": "WMO / public",
        "is_synthetic": True,
        "description": "Rainfall, humidity and wind series from national meteorological services.",
    },
    {
        "id": "usgs-seismic",
        "name": "USGS Seismic Networks",
        "kind": "weather",
        "url": "https://earthquake.usgs.gov/",
        "license": "US Gov / public domain",
        "is_synthetic": True,
        "description": "Ground motion, energy release and tremor telemetry from seismic stations.",
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
        "description": "Verified sightings — shaking, ashfall, sea recession, slope movement.",
    },
    {
        "id": "news-eom",
        "name": "EOM News Wire",
        "kind": "news",
        "url": "",
        "license": "Editorial",
        "is_synthetic": True,
        "description": "Regional advisories — seismic, volcanic, typhoon and heat warnings.",
    },
]

SEED_VERSION = "asia-continental-v1"

# (zone_id, name, region, lat, lon, elevation_m, drainage_capacity_mmh, population, hazard, exposure)
EARTHQUAKE = [
    ("as_jp_tok", "Tokyo Bay Metro", "Japan", 35.68, 139.69, 15.0, 6.0, 37_400_000, "earthquake", 1.35),
    ("as_jp_snd", "Sendai Plain", "Japan", 38.26, 140.87, 6.0, 5.5, 1_100_000, "earthquake", 1.3),
    ("as_tw_hua", "Hualien Fault Zone", "Taiwan", 23.97, 121.61, 10.0, 6.0, 300_000, "earthquake", 1.5),
    ("as_tw_tpe", "Taipei Basin", "Taiwan", 25.03, 121.57, 7.0, 5.5, 7_000_000, "earthquake", 1.35),
    ("as_id_jkt", "Jakarta Basin", "Indonesia", -6.21, 106.85, 8.0, 5.0, 10_600_000, "earthquake", 1.4),
    ("as_id_pdg", "Padang Seismic Zone", "Indonesia", -0.95, 100.35, 2.0, 5.0, 1_000_000, "earthquake", 1.45),
    ("as_ph_mnl", "Manila Metro", "Philippines", 14.60, 120.98, 16.0, 5.5, 13_500_000, "earthquake", 1.4),
    ("as_np_ktm", "Kathmandu Valley", "Nepal", 27.72, 85.32, 1400.0, 7.0, 2_900_000, "earthquake", 1.4),
    ("as_pk_isb", "Islamabad-Rawalpindi", "Pakistan", 33.68, 73.05, 500.0, 6.5, 2_300_000, "earthquake", 1.25),
    ("as_pk_qta", "Quetta Fault Belt", "Pakistan", 30.18, 67.00, 1680.0, 7.5, 1_000_000, "earthquake", 1.3),
    ("as_ir_thr", "Tehran Metro", "Iran", 35.69, 51.39, 1190.0, 6.5, 8_700_000, "earthquake", 1.3),
    ("as_tr_ist", "Istanbul Fault Line", "Türkiye", 41.01, 28.98, 40.0, 5.5, 15_500_000, "earthquake", 1.35),
    ("as_cn_cdg", "Chengdu Basin", "China", 30.57, 104.07, 500.0, 6.0, 21_100_000, "earthquake", 1.25),
    ("as_cn_kmg", "Kunming Fault Belt", "China", 25.04, 102.71, 1890.0, 7.0, 8_500_000, "earthquake", 1.3),
]

TSUNAMI = [
    ("as_jp_kch", "Kochi Surge Coast", "Japan", 33.56, 133.53, 3.0, 4.5, 800_000, "tsunami", 1.5),
    ("as_jp_miy", "Miyagi Coast", "Japan", 38.42, 141.46, 2.0, 4.5, 700_000, "tsunami", 1.5),
    ("as_id_ace", "Banda Aceh", "Indonesia", 5.55, 95.32, 2.0, 4.5, 250_000, "tsunami", 1.55),
    ("as_id_plu", "Palu Bay", "Indonesia", -0.90, 119.85, 1.0, 4.0, 380_000, "tsunami", 1.5),
    ("as_ph_ley", "Leyte Gulf", "Philippines", 11.05, 125.02, 2.0, 4.5, 900_000, "tsunami", 1.5),
    ("as_tw_khs", "Kaohsiung Harbour", "Taiwan", 22.62, 120.28, 2.0, 4.5, 2_700_000, "tsunami", 1.45),
    ("as_lk_cmb", "Colombo Coast", "Sri Lanka", 6.93, 79.85, 3.0, 4.5, 2_300_000, "tsunami", 1.45),
    ("as_lk_gal", "Galle Harbour", "Sri Lanka", 6.03, 80.22, 2.0, 4.5, 100_000, "tsunami", 1.5),
    ("as_mm_ygn", "Yangon Delta", "Myanmar", 16.87, 96.20, 4.0, 4.5, 5_200_000, "tsunami", 1.4),
    ("as_bd_cxb", "Cox's Bazar Coast", "Bangladesh", 21.43, 92.01, 2.0, 4.5, 1_200_000, "tsunami", 1.5),
    ("as_th_phk", "Phuket Andaman", "Thailand", 7.88, 98.39, 3.0, 5.0, 400_000, "tsunami", 1.5),
    ("as_cn_hk", "Hong Kong South", "China", 22.20, 114.10, 5.0, 5.0, 7_500_000, "tsunami", 1.35),
]

VOLCANIC = [
    ("as_id_jog", "Merapi Zone", "Indonesia", -7.54, 110.44, 700.0, 6.5, 4_300_000, "volcanic", 1.5),
    ("as_id_mdn", "Sinabung Zone", "Indonesia", 3.17, 98.39, 1100.0, 7.0, 2_400_000, "volcanic", 1.45),
    ("as_id_dps", "Agung Zone", "Indonesia", -8.41, 115.35, 700.0, 6.5, 830_000, "volcanic", 1.45),
    ("as_id_lpg", "Krakatoa Watch", "Indonesia", -5.55, 105.42, 30.0, 6.0, 1_100_000, "volcanic", 1.5),
    ("as_ph_lgz", "Mayon Zone", "Philippines", 13.26, 123.69, 200.0, 6.0, 500_000, "volcanic", 1.5),
    ("as_ph_bat", "Taal Caldera", "Philippines", 14.01, 120.99, 40.0, 6.0, 2_100_000, "volcanic", 1.5),
    ("as_ph_ang", "Pinatubo Ash Plain", "Philippines", 15.14, 120.35, 400.0, 6.5, 1_500_000, "volcanic", 1.4),
    ("as_jp_kgs", "Sakurajima Zone", "Japan", 31.58, 130.66, 40.0, 6.0, 600_000, "volcanic", 1.45),
    ("as_ru_pk", "Kamchatka Volcanoes", "Russia", 53.02, 158.65, 300.0, 7.0, 180_000, "volcanic", 1.3),
    ("as_cn_chg", "Changbaishan Watch", "China", 42.00, 128.06, 1000.0, 7.0, 800_000, "volcanic", 1.2),
    ("as_jp_oga", "Ogasawara Arc", "Japan", 27.09, 142.19, 10.0, 6.0, 2_000, "volcanic", 1.2),
]

LANDSLIDE = [
    ("as_np_pkr", "Pokhara Valley", "Nepal", 28.21, 83.99, 900.0, 6.5, 500_000, "landslide", 1.5),
    ("as_bt_tmp", "Thimphu Hills", "Bhutan", 27.47, 89.64, 2300.0, 7.5, 110_000, "landslide", 1.4),
    ("as_lk_bad", "Badulla Slope Belt", "Sri Lanka", 6.99, 81.06, 670.0, 6.5, 100_000, "landslide", 1.45),
    ("as_ph_bgw", "Baguio Cordillera", "Philippines", 16.40, 120.59, 1500.0, 7.0, 350_000, "landslide", 1.5),
    ("as_id_bgr", "Bogor Highlands", "Indonesia", -6.60, 106.80, 500.0, 6.5, 1_100_000, "landslide", 1.45),
    ("as_cn_wcn", "Wenchuan Fault Slope", "China", 31.23, 103.58, 1300.0, 7.0, 500_000, "landslide", 1.5),
    ("as_pk_mzf", "Muzaffarabad Hills", "Pakistan", 34.37, 73.47, 700.0, 6.5, 400_000, "landslide", 1.45),
    ("as_jp_nag", "Nagasaki Hills", "Japan", 32.75, 129.88, 100.0, 6.5, 400_000, "landslide", 1.3),
    ("as_mm_mnd", "Mandalay Escarpment", "Myanmar", 21.99, 96.08, 80.0, 6.0, 1_300_000, "landslide", 1.4),
    ("as_vn_lc", "Lao Cai Highlands", "Vietnam", 22.49, 103.97, 900.0, 7.0, 100_000, "landslide", 1.4),
]

DROUGHT = [
    ("as_pk_kch", "Karachi Sindh", "Pakistan", 24.86, 67.01, 8.0, 6.5, 16_900_000, "drought", 1.3),
    ("as_pk_hyd", "Hyderabad Sindh", "Pakistan", 25.40, 68.37, 13.0, 6.5, 1_900_000, "drought", 1.35),
    ("as_lk_jfn", "Jaffna Peninsula", "Sri Lanka", 9.66, 80.02, 3.0, 6.5, 90_000, "drought", 1.4),
    ("as_lk_anu", "Anuradhapura Dry Zone", "Sri Lanka", 8.31, 80.40, 90.0, 6.5, 900_000, "drought", 1.4),
    ("as_th_kkn", "Khon Kaen Plateau", "Thailand", 16.44, 102.84, 150.0, 7.0, 400_000, "drought", 1.35),
    ("as_kh_php", "Phnom Penh Reach", "Cambodia", 11.56, 104.92, 12.0, 6.5, 2_300_000, "drought", 1.3),
    ("as_vn_dla", "Da Lat Highlands", "Vietnam", 11.94, 108.44, 1500.0, 7.0, 250_000, "drought", 1.3),
    ("as_la_vte", "Vientiane Plain", "Laos", 17.97, 102.63, 170.0, 7.0, 950_000, "drought", 1.35),
    ("as_mm_mdl", "Mandalay Dry Belt", "Myanmar", 21.99, 96.08, 80.0, 6.5, 1_300_000, "drought", 1.4),
    ("as_cn_xan", "Xi'an Loess Plateau", "China", 34.34, 108.94, 405.0, 7.0, 12_900_000, "drought", 1.3),
    ("as_ir_krm", "Kerman Basin", "Iran", 30.28, 57.08, 1750.0, 7.5, 600_000, "drought", 1.35),
    ("as_af_kbl", "Kabul Valley", "Afghanistan", 34.56, 69.21, 1790.0, 7.0, 4_600_000, "drought", 1.3),
    ("as_kz_ala", "Almaty Steppe", "Kazakhstan", 43.24, 76.93, 800.0, 7.5, 2_000_000, "drought", 1.3),
    ("as_mn_uba", "Ulaanbaatar Steppe", "Mongolia", 47.89, 106.91, 1350.0, 7.5, 1_500_000, "drought", 1.3),
]

HEATWAVE = [
    ("as_iq_bgd", "Baghdad Heat Dome", "Iraq", 33.32, 44.36, 34.0, 6.0, 8_000_000, "heatwave", 1.35),
    ("as_iq_bsr", "Basra Gulf Coast", "Iraq", 30.51, 47.78, 5.0, 6.0, 2_200_000, "heatwave", 1.4),
    ("as_ir_ahv", "Ahvaz Khuzestan", "Iran", 31.32, 48.67, 20.0, 6.0, 1_300_000, "heatwave", 1.45),
    ("as_kw_kwt", "Kuwait City", "Kuwait", 29.38, 47.99, 5.0, 6.0, 3_100_000, "heatwave", 1.45),
    ("as_qa_doh", "Doha Bay", "Qatar", 25.29, 51.53, 5.0, 6.0, 2_400_000, "heatwave", 1.4),
    ("as_ae_dxb", "Dubai Coast", "UAE", 25.20, 55.27, 5.0, 6.0, 3_600_000, "heatwave", 1.35),
    ("as_sa_ryd", "Riyadh Plateau", "Saudi Arabia", 24.71, 46.68, 600.0, 6.5, 7_000_000, "heatwave", 1.35),
    ("as_pk_lhr", "Lahore Corridor", "Pakistan", 31.55, 74.34, 217.0, 6.0, 13_500_000, "heatwave", 1.35),
    ("as_pk_mtn", "Multan Belt", "Pakistan", 30.20, 71.47, 122.0, 6.0, 1_900_000, "heatwave", 1.4),
    ("as_cn_shg", "Shanghai Megacity", "China", 31.23, 121.47, 4.0, 5.5, 24_900_000, "heatwave", 1.35),
    ("as_cn_whn", "Wuhan Furnace", "China", 30.59, 114.31, 23.0, 5.5, 11_200_000, "heatwave", 1.35),
    ("as_kr_sl", "Seoul Basin", "South Korea", 37.57, 126.98, 38.0, 5.5, 9_700_000, "heatwave", 1.25),
    ("as_kr_dg", "Daegu Hot Valley", "South Korea", 35.87, 128.60, 45.0, 5.5, 2_500_000, "heatwave", 1.35),
]

FLOOD = [
    ("as_bd_dhk", "Dhaka Megacity", "Bangladesh", 23.81, 90.41, 6.0, 4.0, 21_700_000, "flood", 1.5),
    ("as_bd_syl", "Sylhet Basin", "Bangladesh", 24.90, 91.86, 8.0, 4.5, 1_300_000, "flood", 1.5),
    ("as_bd_bag", "Barisal Delta", "Bangladesh", 22.70, 90.37, 3.0, 4.0, 1_700_000, "flood", 1.55),
    ("as_vn_han", "Hanoi Red River", "Vietnam", 21.03, 105.85, 10.0, 5.0, 8_100_000, "flood", 1.35),
    ("as_vn_sgn", "Ho Chi Minh Delta", "Vietnam", 10.82, 106.63, 4.0, 4.0, 9_300_000, "flood", 1.5),
    ("as_th_bkk", "Bangkok Chao Phraya", "Thailand", 13.76, 100.50, 3.0, 4.0, 10_700_000, "flood", 1.45),
    ("as_th_ayt", "Ayutthaya Plain", "Thailand", 14.35, 100.58, 4.0, 4.5, 100_000, "flood", 1.4),
    ("as_mm_bgo", "Bago Basin", "Myanmar", 17.34, 96.47, 10.0, 5.0, 500_000, "flood", 1.4),
    ("as_cn_gz", "Guangzhou Pearl Delta", "China", 23.13, 113.26, 5.0, 4.5, 14_900_000, "flood", 1.45),
    ("as_cn_cq", "Chongqing Gorges", "China", 29.56, 106.55, 240.0, 5.5, 8_400_000, "flood", 1.35),
    ("as_pk_suk", "Sukkur Indus Reach", "Pakistan", 27.70, 68.85, 65.0, 5.0, 500_000, "flood", 1.4),
    ("as_pk_psh", "Peshawar Kabul", "Pakistan", 34.02, 71.58, 330.0, 5.5, 2_300_000, "flood", 1.35),
    ("as_np_brg", "Birgunj Terai", "Nepal", 27.00, 84.87, 80.0, 5.0, 260_000, "flood", 1.35),
    ("as_lk_kandy", "Kandy Central", "Sri Lanka", 7.29, 80.63, 500.0, 5.5, 120_000, "flood", 1.25),
    ("as_jp_fkk", "Fukuoka Urban", "Japan", 33.59, 130.40, 5.0, 5.0, 1_600_000, "flood", 1.3),
]

CYCLONE = [
    ("as_ph_smr", "Samar Coast", "Philippines", 11.71, 125.04, 3.0, 4.5, 800_000, "cyclone", 1.5),
    ("as_ph_cat", "Catanduanes Alley", "Philippines", 13.71, 124.25, 10.0, 4.5, 260_000, "cyclone", 1.55),
    ("as_vn_dng", "Da Nang Coast", "Vietnam", 16.05, 108.22, 5.0, 4.5, 1_100_000, "cyclone", 1.45),
    ("as_vn_ntr", "Nha Trang Bay", "Vietnam", 12.24, 109.19, 4.0, 4.5, 400_000, "cyclone", 1.45),
    ("as_bd_khl", "Khulna Sundarbans", "Bangladesh", 22.85, 89.53, 2.0, 4.0, 1_500_000, "cyclone", 1.55),
    ("as_cn_hak", "Haikou Hainan", "China", 20.04, 110.34, 5.0, 4.5, 1_000_000, "cyclone", 1.5),
    ("as_cn_sz", "Shenzhen Bay", "China", 22.54, 114.06, 4.0, 4.5, 17_600_000, "cyclone", 1.4),
    ("as_tw_tai", "Tainan Coast", "Taiwan", 23.00, 120.21, 3.0, 4.5, 1_900_000, "cyclone", 1.45),
    ("as_jp_okn", "Okinawa Belt", "Japan", 26.33, 127.80, 5.0, 4.5, 1_400_000, "cyclone", 1.45),
    ("as_kr_jju", "Jeju Channel", "South Korea", 33.49, 126.53, 2.0, 4.5, 700_000, "cyclone", 1.35),
]

WILDFIRE = [
    ("as_id_plk", "Palangkaraya Peat", "Indonesia", -2.21, 113.91, 25.0, 6.0, 300_000, "wildfire", 1.5),
    ("as_id_pbr", "Riau Haze Belt", "Indonesia", 0.51, 101.45, 10.0, 6.0, 1_100_000, "wildfire", 1.45),
    ("as_my_kch", "Kuching Borneo", "Malaysia", 1.55, 110.34, 20.0, 6.0, 800_000, "wildfire", 1.4),
    ("as_th_cmi", "Chiang Mai Smog Bowl", "Thailand", 18.79, 98.98, 310.0, 6.5, 1_300_000, "wildfire", 1.45),
    ("as_th_msh", "Mae Hong Son", "Thailand", 19.30, 97.97, 280.0, 6.5, 60_000, "wildfire", 1.4),
    ("as_ru_kra", "Krasnoyarsk Taiga", "Russia", 56.01, 92.87, 150.0, 6.5, 1_100_000, "wildfire", 1.3),
    ("as_cn_hoh", "Hohhot Steppe", "China", 40.84, 111.75, 1050.0, 7.0, 3_500_000, "wildfire", 1.3),
    ("as_mn_drn", "Dornod Grassland", "Mongolia", 47.96, 110.58, 900.0, 7.0, 80_000, "wildfire", 1.4),
]

ALL_ZONES = EARTHQUAKE + TSUNAMI + VOLCANIC + LANDSLIDE + DROUGHT + HEATWAVE + FLOOD + CYCLONE + WILDFIRE


def _earthquake_arc(hours: int, phase: float, seed: int, intensity: float = 1.0) -> dict:
    """Seismic episode: mainshock ~t=0.6, Omori-style aftershock decay."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    main = 0.55 + 0.05 * phase
    accel = 0.06 + 0.75 * np.exp(-((t - main) ** 2) / 0.002) * intensity
    accel += 0.10 * np.exp(-((t - main) ** 2) / 0.04) * np.clip(1 - (t - main) * 4, 0, 1)
    accel += rng.normal(0, 0.015, hours)
    energy = 14 * np.exp(-((t - main) ** 2) / 0.002) * intensity
    energy += 420 * np.exp(-(np.clip(t - main, 0, 1) / 0.35)) * np.clip(t - main, 0, None) * intensity
    energy += rng.normal(0, 4, hours)
    return {"ground_accel": np.clip(accel, 0.02, 1.0), "seismic_energy": np.clip(energy, 0, None)}


def _tsunami_arc(hours: int, phase: float, seed: int, intensity: float = 1.0) -> dict:
    """Offshore sea-floor event: single large energy release then quiet."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    main = 0.68 + 0.04 * phase
    energy = 340 * np.exp(-((t - main) ** 2) / 0.0008) * intensity
    energy += rng.normal(0, 6, hours)
    return {"seismic_energy": np.clip(energy, 0, None)}


def _volcanic_arc(hours: int, phase: float, seed: int, intensity: float = 1.0) -> dict:
    """Eruption escalation: tremor ramps, SO2 flux climbs, plume lifts late."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    ramp = np.clip((t - 0.45 + phase * 0.04) / 0.5, 0, 1)
    tremor = (0.25 + 1.6 * ramp**2) * intensity
    so2 = (0.6 + 4.0 * ramp**2) * intensity
    plume = 1.2 + 8.0 * np.clip(ramp - 0.45, 0, 0.55) * intensity
    tremor += rng.normal(0, 0.05, hours)
    return {
        "volcanic_tremor": np.clip(tremor, 0, 2.2),
        "so2_flux": np.clip(so2, 0, 5.2),
        "ash_plume_km": np.clip(plume, 0, 10.0),
    }


def _landslide_arc(hours: int, phase: float, seed: int, peak_mm: float = 62.0) -> dict:
    """Monsoon burst on saturated slopes — flood physics with a sharper trigger."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    burst = peak_mm * np.exp(-((t - (0.8 + phase * 0.05)) ** 2) / 0.016)
    background = 3.0 + 1.5 * np.sin(2 * np.pi * t * 2 + phase * 3)
    rain = np.clip(burst + background + rng.normal(0, 1.2, hours), 0, None)
    humidity = np.clip(70 + rain * 0.65, 55, 98)
    wind = np.clip(12 + rain * 0.25, 5, 40)
    soil = np.clip(5.0 + rain * 0.3, 1.0, 12.0)
    return {"rainfall_mm": rain, "humidity": humidity, "wind_kmh": wind, "soil_anomaly": soil}


def _drought_arc(hours: int, phase: float, seed: int) -> dict:
    """Monsoon-break / dry-belt descent: rain collapses, soil dries, humidity drops."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    rain = np.clip(10 * (1 - np.clip((t + phase * 0.04) * 1.3, 0, 1)) ** 2 + rng.normal(0, 0.6, hours), 0, 12)
    humidity = np.clip(52 - 26 * np.clip((t + phase * 0.05) * 1.2, 0, 1) + rng.normal(0, 2, hours), 12, 60)
    wind = np.clip(10 + 6 * np.sin(2 * np.pi * t * 1.5 + phase), 4, 30)
    soil = np.clip(6.0 - 5.0 * np.clip((t + phase * 0.06) * 1.1, 0, 1) + rng.normal(0, 0.2, hours), 0.3, 7.0)
    return {"rainfall_mm": rain, "humidity": humidity, "wind_kmh": wind, "soil_anomaly": soil}


def _heatwave_arc(hours: int, phase: float, seed: int) -> dict:
    """Heat-dome: humidity and wind collapse, zero rain, soil desiccates."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, hours)
    humidity = np.clip(58 - 40 * np.clip((t + phase * 0.06) * 1.1, 0, 1) + rng.normal(0, 2, hours), 10, 60)
    wind = np.clip(12 - 7 * np.clip((t + phase * 0.06) * 1.1, 0, 1) + rng.normal(0, 1, hours), 2, 18)
    rain = np.clip(0.4 + rng.normal(0, 0.2, hours), 0, 1.2)
    soil = np.clip(4.5 - 4.0 * np.clip((t + phase * 0.07) * 1.1, 0, 1) + rng.normal(0, 0.15, hours), 0.2, 5.0)
    return {"rainfall_mm": rain, "humidity": humidity, "wind_kmh": wind, "soil_anomaly": soil}


def _rolling(x: np.ndarray, w: int) -> np.ndarray:
    kernel = np.ones(w) / w
    return np.convolve(x, kernel, mode="same")


def generate(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=72)
    hours = 72

    zones = []
    for i, (zid, name, region, lat, lon, elev, cap, pop, hazard, exposure) in enumerate(ALL_ZONES):
        phase = (i % 5) * 0.07
        seed = i * 13 + 7
        if hazard == "flood":
            arc = _flood_arc(hours, phase=phase, seed=seed, peak_mm=52.0)
        elif hazard == "cyclone":
            arc = _cyclone_arc(hours, phase=phase, seed=seed, intensity=0.75 + 0.42 * exposure)
        elif hazard == "wildfire":
            arc = _wildfire_arc(hours, phase=phase, seed=seed)
        elif hazard == "landslide":
            arc = _landslide_arc(hours, phase=phase, seed=seed)
        elif hazard == "drought":
            arc = _drought_arc(hours, phase=phase, seed=seed)
        elif hazard == "heatwave":
            arc = _heatwave_arc(hours, phase=phase, seed=seed)
        elif hazard == "earthquake":
            arc = _earthquake_arc(hours, phase=phase, seed=seed, intensity=0.7 + 0.5 * exposure)
        elif hazard == "tsunami":
            arc = _tsunami_arc(hours, phase=phase, seed=seed, intensity=0.7 + 0.5 * exposure)
        else:  # volcanic
            arc = _volcanic_arc(hours, phase=phase, seed=seed, intensity=0.6 + 0.6 * exposure)
        zones.append(_build_zone(zid, name, region, lat, lon, elev, cap, pop, hazard, exposure, arc, start, hours))

    return {
        "version": SEED_VERSION,
        "generated_at": now.isoformat(),
        "is_synthetic": True,
        "scope": "asia",
        "sources": SOURCES,
        "zones": zones,
    }


def _build_zone(zid, name, region, lat, lon, elev, cap, pop, hazard, exposure, arc, start, hours) -> dict:
    seismic = None
    if hazard in ("earthquake", "tsunami", "volcanic"):
        seismic = []
        for t in range(hours):
            for metric, mult in (
                ("ground_accel", 1.0),
                ("seismic_energy", 1.0),
                ("volcanic_tremor", 1.0),
                ("so2_flux", 1.0),
                ("ash_plume_km", 1.0),
            ):
                if metric not in arc:
                    continue
                seismic.append(
                    {
                        "captured_at": (start + timedelta(hours=t)).isoformat(),
                        "source_id": "usgs-seismic",
                        "metric": metric,
                        "value": round(float(arc[metric][t] * mult), 4),
                        "unit": "g"
                        if metric == "ground_accel"
                        else (
                            "GJ"
                            if metric == "seismic_energy"
                            else ("km" if metric == "ash_plume_km" else "kt/d" if metric == "so2_flux" else "um/s")
                        ),
                        "is_synthetic": True,
                    }
                )

    if hazard in ("flood", "landslide"):
        rain = arc["rainfall_mm"]
        sat = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "soil_moisture_anomaly": round(float(arc["soil_anomaly"][t]), 3),
                "surface_water_index": round(float(np.clip(arc["soil_anomaly"][t] / 9.0, 0, 1)), 3),
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
                "source_id": "wmo-gts",
            }
            for t in range(hours)
        ]
    elif hazard in ("wildfire", "drought", "heatwave"):
        sat = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "soil_moisture_anomaly": round(float(arc["soil_anomaly"][t]), 3),
                "surface_water_index": round(float(np.clip(arc["soil_anomaly"][t] / 9.0, 0.02, 0.6)), 3),
                "source_id": "viiirs-thermal" if t % 3 == 0 else "gpm-nasa",
            }
            for t in range(0, hours, 2)
        ]
        water = []
    else:  # seismic hazards — quiet weather backdrop, thermal proxy on VIIRS
        sat = [
            {
                "captured_at": (start + timedelta(hours=t)).isoformat(),
                "soil_moisture_anomaly": round(float(np.clip(6.0 - 2.0 * np.sin(t / 7), 2.0, 8.0)), 3),
                "surface_water_index": round(float(np.clip(0.45 + 0.1 * np.sin(t / 9), 0.2, 0.6)), 3),
                "source_id": "viiirs-thermal" if t % 3 == 0 else "gpm-nasa",
            }
            for t in range(0, hours, 2)
        ]
        water = []

    citizen = _citizen_reports(zid, name, hazard, arc, start, hours, exposure)

    if hazard in ("earthquake", "tsunami", "volcanic"):
        rain_v = np.full(hours, 1.2)
        hum_v = np.full(hours, 62.0)
        wind_v = np.full(hours, 10.0)
    else:
        rain_v, hum_v, wind_v = arc["rainfall_mm"], arc["humidity"], arc["wind_kmh"]

    weather = [
        {
            "captured_at": (start + timedelta(hours=t)).isoformat(),
            "rainfall_mm": round(float(rain_v[t]), 2),
            "rain_forecast_mm": round(float(rain_v[min(hours - 1, t + 6)] * 0.94), 2),
            "humidity": round(float(hum_v[t]), 1),
            "wind_kmh": round(float(wind_v[t]), 1),
            "source_id": "usgs-seismic" if hazard in ("earthquake", "tsunami", "volcanic") else "wmo-gts",
        }
        for t in range(hours)
    ]
    news = [
        {
            "captured_at": (start + timedelta(hours=58)).isoformat(),
            "tags": {
                "flood": ["monsoon", "asia", "advisory"],
                "cyclone": ["typhoon", "asia", "landfall"],
                "wildfire": ["wildfire", "asia", "haze"],
                "earthquake": ["seismic", "asia", "episode"],
                "tsunami": ["tsunami", "asia", "sea-state"],
                "volcanic": ["volcanic", "asia", "eruption"],
                "landslide": ["landslide", "asia", "slope"],
                "drought": ["drought", "asia", "water"],
                "heatwave": ["heatwave", "asia", "heat-dome"],
            }[hazard],
            "warning_level": 3 if hazard in ("cyclone", "tsunami", "earthquake") else 2,
            "credibility": 0.85,
            "source_id": "news-eom",
        }
    ]

    zone = {
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
    if seismic:
        zone["seismic"] = seismic
    return zone


def _citizen_reports(zid, name, hazard, arc, start, hours, exposure=1.0) -> list[dict]:
    humidity = arc.get("humidity")
    wind = arc.get("wind_kmh")
    rain = arc.get("rainfall_mm")
    out = []
    for t in range(36, hours, 3):
        if hazard in ("flood", "landslide"):
            pressure = np.clip((_rolling(rain, 6)[t] * 6 / 22.0) - 6.0, 0, 8)
            if pressure <= 0.8:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "slope_movement" if hazard == "landslide" else "waterlogging",
                    "severity_hint": int(np.clip(pressure / 2, 1, 4)),
                    "text": f"{'Slope movement' if hazard == 'landslide' else 'Waterlogging'} reported near {name}",
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
        elif hazard == "wildfire":
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
        elif hazard == "earthquake":
            accel = arc["ground_accel"][t]
            if accel < 0.18:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "shaking",
                    "severity_hint": int(np.clip(accel * 6, 1, 5)),
                    "text": f"Verified shaking reported in {name} metro",
                    "verified": bool(accel > 0.25),
                    "source_id": "civic-reports",
                }
            )
        elif hazard == "tsunami":
            energy = arc["seismic_energy"][t]
            if energy < 40:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "sea_state",
                    "severity_hint": int(np.clip(energy / 90, 1, 5)),
                    "text": f"Sea recession reported on {name} shoreline",
                    "verified": bool(energy > 90),
                    "source_id": "civic-reports",
                }
            )
        elif hazard == "volcanic":
            plume = arc["ash_plume_km"][t]
            if plume < 2.5:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "ashfall",
                    "severity_hint": int(np.clip(plume / 2.2, 1, 5)),
                    "text": f"Ashfall reported in {name} sector",
                    "verified": bool(plume > 4.0),
                    "source_id": "civic-reports",
                }
            )
        elif hazard == "drought":
            dry_pressure = np.clip((60.0 - humidity[t]) * exposure, 0, 50)
            if dry_pressure <= 24:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "water_scarcity",
                    "severity_hint": int(np.clip(dry_pressure / 12.0, 1, 5)),
                    "text": f"Water scarcity reported in {name} dry belt",
                    "verified": bool(dry_pressure > 30),
                    "source_id": "civic-reports",
                }
            )
        else:  # heatwave
            hot_pressure = np.clip((60.0 - humidity[t]) * exposure, 0, 50)
            if hot_pressure <= 26:
                continue
            out.append(
                {
                    "location_id": zid,
                    "reported_at": (start + timedelta(hours=t)).isoformat(),
                    "category": "heat_illness",
                    "severity_hint": int(np.clip(hot_pressure / 12.0, 1, 5)),
                    "text": f"Heat illness reported in {name} hot corridor",
                    "verified": bool(hot_pressure > 32),
                    "source_id": "civic-reports",
                }
            )
    return out


if __name__ == "__main__":
    data = generate()
    with open("app/data/seeds/asia_seed.json", "w") as f:
        json.dump(data, f, indent=1)
    counts = {}
    for z in data["zones"]:
        counts[z["hazard_type"]] = counts.get(z["hazard_type"], 0) + 1
    print(f"wrote {len(data['zones'])} zones to asia_seed.json: {counts}")
