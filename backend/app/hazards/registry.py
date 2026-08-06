"""Hazard registry — one-stop lookup for the core engine."""

from __future__ import annotations

from app.hazards.cyclone import CYCLONE
from app.hazards.drought import DROUGHT
from app.hazards.earthquake import EARTHQUAKE
from app.hazards.flood import FLOOD
from app.hazards.heatwave import HEATWAVE
from app.hazards.landslide import LANDSLIDE
from app.hazards.spec import HazardSpec
from app.hazards.tsunami import TSUNAMI
from app.hazards.volcanic import VOLCANIC
from app.hazards.wildfire import WILDFIRE

HAZARDS: dict[str, HazardSpec] = {
    h.id: h
    for h in (
        FLOOD,
        WILDFIRE,
        CYCLONE,
        EARTHQUAKE,
        TSUNAMI,
        VOLCANIC,
        LANDSLIDE,
        DROUGHT,
        HEATWAVE,
    )
}
DEFAULT_HAZARD = "flood"


def get_hazard(hazard_id: str | None) -> HazardSpec:
    """Resolve a hazard spec; unknown ids fall back to flood (never crash)."""
    return HAZARDS.get((hazard_id or DEFAULT_HAZARD).strip().lower(), FLOOD)


def hazard_ids() -> list[str]:
    return sorted(HAZARDS)
