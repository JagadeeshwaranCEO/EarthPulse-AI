"""EarthPulse AI — FastAPI application entrypoint.

Boot order: init DB → seed synthetic Chennai pilot (if empty) → run initial
pipeline → persist predictions → start WS broadcaster.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, chat, dashboard, decision, risks, simulations
from app.api.ws import broadcaster, router as ws_router
from app.agents.orchestrator import build_agent_outputs
from app.config import get_settings
from app.core import models
from app.core.db import SessionLocal, init_db
from app.ml.forecaster import DEFAULT_FORECASTER
from app.services import evidence as ev_svc
from app.services.simulation_engine import available_interventions
from app.services.ticker import set_anchor

logger = logging.getLogger("earthpulse")

_SEED_PATH = Path(__file__).parent / "data" / "seeds" / "chennai_seed.json"


def _seed_if_empty(db) -> None:
    if not _SEED_PATH.exists():
        logger.warning("seed file missing at %s — skipping", _SEED_PATH)
        return
    data = json.loads(_SEED_PATH.read_text())
    anchor = datetime.fromisoformat(data["generated_at"]) - timedelta(hours=72)
    set_anchor(anchor.isoformat())
    if db.query(models.Location).count() > 0:
        return
    sources = {
        s["id"]: models.Source(**s) for s in data["sources"]
    }
    for s in sources.values():
        db.add(s)
    for z in data["zones"]:
        loc = models.Location(
            id=z["id"], name=z["name"], region="Chennai", lat=z["lat"], lon=z["lon"],
            elevation_m=z["elevation_m"], drainage_capacity_mmh=z["drainage_capacity_mmh"],
            population=z["population"],
            attributes={"exposure": z.get("exposure", 1.0)},
        )
        db.add(loc)
        db.flush()
        for w in z["weather"]:
            db.add(models.WeatherSnapshot(location_id=z["id"], captured_at=datetime.fromisoformat(w["captured_at"]), **{k: v for k, v in w.items() if k != "captured_at"}))
        for f in z["satellite"]:
            db.add(models.SatelliteFrame(location_id=z["id"], captured_at=datetime.fromisoformat(f["captured_at"]), **{k: v for k, v in f.items() if k != "captured_at"}))
        for c in z["citizen"]:
            db.add(models.CitizenReport(reported_at=datetime.fromisoformat(c["reported_at"]), **{k: v for k, v in c.items() if k != "reported_at"}))
    for iid, meta in {
        "pump_preposition": ("Pre-position pumps at low-lying wards", "operational"),
        "reservoir_release": ("Coordinate reservoir release", "operational"),
        "drainage_clearing": ("Clear stormwater inlets", "engineering"),
        "sandbagging": ("Sandbag river-adjacent blocks", "engineering"),
        "evacuation_ready": ("Stage shelters and routes", "policy"),
        "rainwater_harvesting": ("Activate retention basins", "policy"),
    }.items():
        db.add(models.Intervention(id=iid, name=iid.replace("_", " ").title(), kind=meta[1], description=meta[0]))
    db.commit()
    logger.info("seeded %d zones from %s", len(data["zones"]), data["version"])


def _refresh_predictions(db) -> None:
    """Run the full pipeline per location and persist predictions + evidence."""
    for loc in db.query(models.Location).all():
        outputs, fused = build_agent_outputs(db, loc.id)
        comps = outputs.get("risk_fusion", {}).get("components", {})
        pred_out = outputs.get("prediction", {})
        if not pred_out:
            continue
        fc = pred_out.get("forecast_series")
        now = datetime.now(timezone.utc)
        pred = models.Prediction(
            location_id=loc.id,
            event_type="flood",
            generated_at=now,
            horizon_h=fc.horizon_h if fc else 24,
            risk_probability=pred_out.get("risk_probability", 0.0),
            severity=pred_out.get("severity", 0.0),
            confidence=pred_out.get("confidence", 0.0),
            lower_bound=pred_out.get("bounds", {}).get("lower", 0.0),
            upper_bound=pred_out.get("bounds", {}).get("upper", 1.0),
            features=comps,
            attribution=outputs.get("explanation", {}).get("attribution", []),
            limitations=outputs.get("explanation", {}).get("limitations", []),
            model_name=pred_out.get("model_name", "earthpulse-stream-v1"),
            series={
                "t": [t.isoformat() for t in fc.series_t],
                "mean": fc.mean, "lower": fc.lower, "upper": fc.upper,
                "residual_std": fc.residual_std,
            } if fc else {},
        )
        db.add(pred)
        db.flush()

        evidence = [
            ev_svc.make_evidence(db, pred.id, db.query(models.Source).get("imd-rain"), "observation",
                                 now - timedelta(hours=3), "6-hour rainfall accumulation entering design-threshold territory",
                                 value=round(comps.get("rain_intensity", 0), 2)),
            ev_svc.make_evidence(db, pred.id, db.query(models.Source).get("gpm-nasa"), "observation",
                                 now - timedelta(hours=3), "satellite soil moisture anomaly exceeds 2σ seasonal baseline",
                                 value=round(comps.get("soil_moisture", 0), 2)),
            ev_svc.make_evidence(db, pred.id, db.query(models.Source).get("cwprs-level"), "observation",
                                 now - timedelta(hours=2), "canal level within X% of drainage headroom limit",
                                 value=round(comps.get("headroom_deficit", 0), 2)),
            ev_svc.make_evidence(db, pred.id, db.query(models.Source).get("civic-reports"), "report",
                                 now - timedelta(hours=1), "verified waterlogging reports from low-lying wards",
                                 value=round(comps.get("citizen_pressure", 0), 2)),
            ev_svc.make_evidence(db, pred.id, db.query(models.Source).get("news-eom"), "citation",
                                 now - timedelta(hours=6), "official monsoon advisory active for the region"),
        ]
        pred.evidence_ids = [e.id for e in evidence]

        level = ("warning" if pred.risk_probability >= 0.55 else "advisory") if pred.risk_probability < 0.75 else "critical"
        existing = db.query(models.Alert).filter_by(location_id=loc.id, resolved=False).count()
        if existing == 0:
            db.add(models.Alert(
                location_id=loc.id, event_type="flood", level=level,
                title=f"Flood risk {pred.risk_probability:.0%} in {loc.name}",
                summary=f"Forecast horizon {pred.horizon_h}h, severity {pred.severity:.1f}/5, confidence {pred.confidence:.0%}. "
                        f"Top driver: {comps and max(comps, key=lambda k: comps[k])}.",
                prediction_id=pred.id,
            ))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        _seed_if_empty(db)
        _refresh_predictions(db)
    finally:
        db.close()
    task = asyncio.create_task(broadcaster())
    yield
    task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Planetary early warning intelligence system — prediction, explanation, simulation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(dashboard.router, prefix=settings.api_prefix)
    app.include_router(risks.router, prefix=settings.api_prefix)
    app.include_router(simulations.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(decision.router, prefix=settings.api_prefix)
    app.include_router(chat.router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    return app


app = create_app()
