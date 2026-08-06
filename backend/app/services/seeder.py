"""Seed loader shared by boot and the live scope-switch endpoint.

`seed_zones(db, data, scope)` inserts sources + zones + observations into an
existing schema. `reseed(db, scope)` clears location-scoped rows first, so an
operator can switch the command theatre (chennai ↔ tamilnadu) at runtime.

Honesty principle preserved: the synthetic flag is stamped on every Source row
and surfaced downstream in provenance.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.core import models
from app.services.ticker import set_anchor

logger = logging.getLogger("earthpulse")

_SEED_FILES = {
    "chennai": Path(__file__).parent.parent / "data" / "seeds" / "chennai_seed.json",
    "tamilnadu": Path(__file__).parent.parent / "data" / "seeds" / "tamilnadu_seed.json",
    "wildfire": Path(__file__).parent.parent / "data" / "seeds" / "wildfire_seed.json",
    "india": Path(__file__).parent.parent / "data" / "seeds" / "india_seed.json",
    "asia": Path(__file__).parent.parent / "data" / "seeds" / "asia_seed.json",
}

_SCOPED = (
    models.Location,
    models.WeatherSnapshot,
    models.SatelliteFrame,
    models.CitizenReport,
    models.Source,
    models.Event,
    models.Prediction,
    models.EvidenceObject,
    models.Alert,
    models.SimulationRun,
    models.IngestedDatum,
    models.PulseScore,
    models.Intervention,
)


def seed_path(scope: str) -> Path:
    return _SEED_FILES.get(scope, _SEED_FILES["chennai"])


def load_seed(scope: str) -> dict:
    path = seed_path(scope)
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text())
    if data.get("scope") != scope and scope == "tamilnadu":
        pass  # tolerate legacy chennai seed packaging
    return data


def _seed_zones(db: Session, data: dict, scope: str) -> None:
    anchor = datetime.fromisoformat(data["generated_at"]) - timedelta(hours=72)
    set_anchor(anchor.isoformat())

    sources = {s["id"]: models.Source(**s) for s in data["sources"]}
    for s in sources.values():
        db.add(s)

    from app.hazards.registry import HAZARDS

    interventions = {i["id"]: i for h in HAZARDS.values() for i in h.interventions}
    for iid, inv in interventions.items():
        db.add(models.Intervention(id=iid, name=inv["name"], kind=inv["kind"], description=inv["description"]))

    for z in data["zones"]:
        loc = models.Location(
            id=z["id"],
            name=z["name"],
            region=z.get("region", "Chennai"),
            lat=z["lat"],
            lon=z["lon"],
            elevation_m=z["elevation_m"],
            drainage_capacity_mmh=z["drainage_capacity_mmh"],
            population=z["population"],
            hazard_type=z.get("hazard_type", "flood"),
            attributes={"exposure": z.get("exposure", 1.0), "scope": scope},
        )
        db.add(loc)
        db.flush()
        for w in z["weather"]:
            db.add(
                models.WeatherSnapshot(
                    location_id=z["id"],
                    captured_at=datetime.fromisoformat(w["captured_at"]),
                    **{k: v for k, v in w.items() if k != "captured_at"},
                )
            )
        for f in z["satellite"]:
            db.add(
                models.SatelliteFrame(
                    location_id=z["id"],
                    captured_at=datetime.fromisoformat(f["captured_at"]),
                    **{k: v for k, v in f.items() if k != "captured_at"},
                )
            )
        for c in z["citizen"]:
            db.add(
                models.CitizenReport(
                    reported_at=datetime.fromisoformat(c["reported_at"]),
                    **{k: v for k, v in c.items() if k != "reported_at"},
                )
            )
        for d in z.get("seismic", []):
            db.add(
                models.IngestedDatum(
                    location_id=z["id"],
                    captured_at=datetime.fromisoformat(d["captured_at"]),
                    source_id=d["source_id"],
                    metric=d["metric"],
                    value=d["value"],
                    unit=d.get("unit", ""),
                    is_synthetic=d.get("is_synthetic", True),
                )
            )
    db.commit()
    logger.info("seeded %d zones for scope=%s (%s)", len(data["zones"]), scope, data.get("version"))


def empty_scoped(db: Session) -> None:
    for model in reversed(_SCOPED):
        db.query(model).delete()
    db.commit()


def reseed(db: Session, scope: str) -> dict:
    """Wipe location-scoped data and seed a fresh theatre. Returns summary."""
    data = load_seed(scope)
    empty_scoped(db)
    _seed_zones(db, data, scope)
    return {"scope": scope, "zones": len(data["zones"]), "version": data.get("version")}


def seed_if_empty(db: Session, settings: Settings) -> bool:
    if db.query(models.Location).count() > 0:
        return False
    try:
        data = load_seed(settings.scope)
    except FileNotFoundError:
        logger.warning("seed file missing — skipping seed")
        return False
    _seed_zones(db, data, settings.scope)
    return True
