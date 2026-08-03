"""Ingestion registry — configure adapters, write frames, report status.

Writing maps each typed frame into the right table:
  rainfall/humidity/wind        → WeatherSnapshot (feeds forecaster features)
  soil_moisture/surface_water   → SatelliteFrame
  everything else               → IngestedDatum archive
Live adapters write under *_live source ids so provenance stays honest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import models
from app.services.ingest.base import IngestedFrame
from app.services.ingest.gpm import GPMAdapter
from app.services.ingest.imd import IMDAdapter
from app.services.ingest.reservoir import ReservoirAdapter

ADAPTERS: dict[str, object] = {
    ad.id: ad for ad in (IMDAdapter(), GPMAdapter(), ReservoirAdapter())
}


def configure_all() -> None:
    s = get_settings()
    for ad in ADAPTERS.values():
        endpoint = getattr(s, ad.endpoint_attr, "")
        token = getattr(s, ad.token_attr, "")
        ad.configure(endpoint, token)


def _locations(db) -> list[dict]:
    return [
        {"id": l.id, "lat": l.lat, "lon": l.lon, "region": l.region,
         "exposure": (l.attributes or {}).get("exposure", 1.0)}
        for l in db.query(models.Location).all()
    ]


def _write_frames(db: Session, frames: Iterable[IngestedFrame]) -> int:
    n = 0
    now = datetime.now(timezone.utc)
    for f in frames:
        ts = f.captured_at or now
        if f.metric in {"rainfall_mm", "rain_forecast_mm", "humidity", "wind_kmh"}:
            db.add(models.WeatherSnapshot(location_id=f.location_id, captured_at=ts,
                                          source_id=f.source_id, **{f.metric: f.value}))
        elif f.metric in {"soil_moisture_anomaly", "surface_water_index"}:
            db.add(models.SatelliteFrame(location_id=f.location_id, captured_at=ts,
                                         source_id=f.source_id, **{f.metric: f.value}))
        else:
            db.add(models.IngestedDatum(location_id=f.location_id, captured_at=ts,
                                        source_id=f.source_id, metric=f.metric,
                                        value=f.value, unit=f.unit, is_synthetic=f.is_synthetic))
        n += 1
    db.commit()
    return n


def ingest_once(db: Session, adapters: list[str] | None = None, since: datetime | None = None) -> dict:
    configure_all()
    locations = _locations(db)
    if not locations:
        return {}
    now = datetime.now(timezone.utc)
    result = {}
    for name, ad in ADAPTERS.items():
        if adapters and name not in adapters:
            continue
        frames = ad.fetch(locations, since)
        written = _write_frames(db, frames)
        result[name] = {"mode": "live" if ad.is_live else "demo",
                        "rows": written, "at": now.isoformat()}
    return result


def statuses() -> list[dict]:
    configure_all()
    return [ad.status().__dict__ for ad in ADAPTERS.values()]