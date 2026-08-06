"""Hazard-aware alert levels shared across the API surface."""

from __future__ import annotations

from app.hazards.registry import get_hazard


def level_for(hazard_id: str | None, probability: float) -> str:
    return get_hazard(hazard_id).level(probability)
