"""EarthPulse AI — FastAPI application entrypoint.

Boot order: init DB → seed synthetic Chennai pilot (if empty) → run initial
pipeline → persist predictions → start WS broadcaster.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import agents, chat, dashboard, data, decision, risks, scope, simulations, validation
from app.api.ws import broadcaster, router as ws_router
from app.config import get_settings
from app.core.db import SessionLocal, init_db
from app.services.refresh import refresh_predictions
from app.services.seeder import seed_if_empty

logger = logging.getLogger("earthpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db, get_settings())
        refresh_predictions(db)
    finally:
        db.close()
    if get_settings().ws_enabled:
        task = asyncio.create_task(broadcaster())
        yield
        task.cancel()
    else:
        yield


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
    app.include_router(scope.router, prefix=settings.api_prefix)
    app.include_router(data.router, prefix=settings.api_prefix)
    app.include_router(validation.router, prefix=settings.api_prefix)
    app.include_router(chat.router, prefix=settings.api_prefix)
    app.include_router(ws_router)
    return app


app = create_app()
