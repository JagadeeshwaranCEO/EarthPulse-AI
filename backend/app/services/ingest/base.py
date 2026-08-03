"""Data-source adapters — the seam where real telemetry attaches.

Each adapter defines a stable contract (`fetch(locations, since) → frames`) and
a live endpoint. Without credentials it runs in **honest demo mode**: it emits
deterministic, provenance-tagged synthetic frames derived from the zone's own
recent telemetry, so the full pipeline is testable end-to-end while the
`is_synthetic` flag never lies. When an endpoint+token is configured, the same
adapter fetches real data and re-labels the source as real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx


@dataclass
class IngestedFrame:
    location_id: str
    captured_at: datetime
    metric: str
    value: float
    source_id: str
    unit: str = ""
    is_synthetic: bool = True


@dataclass
class AdapterStatus:
    id: str
    kind: str
    mode: str  # live | demo
    description: str
    last_ingest: datetime | None = None
    rows_written: int = 0


class DataSourceAdapter:
    id: str = "base"
    kind: str = "weather"
    description: str = ""
    endpoint_attr: str = ""
    token_attr: str = ""
    endpoint: str = ""
    token: str = ""

    def configure(self, endpoint: str, token: str) -> None:
        self.endpoint = endpoint.strip() if endpoint else ""
        self.token = token.strip() if token else ""
        self._live = bool(self.endpoint)

    @property
    def is_live(self) -> bool:
        return self._live

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            id=self.id, kind=self.kind, mode="live" if self.is_live else "demo",
            description=self.description,
        )

    def fetch(self, locations: list[dict], since: datetime | None = None) -> list[IngestedFrame]:
        """Return frames; live path preferred, demo fallback otherwise (still honest)."""
        if self.is_live:
            try:
                return self._fetch_live(locations, since)
            except Exception as exc:  # network/parse failure → labeled synthetic fallback
                self._last_error = str(exc)
                return self._mark_demo(self._fetch_demo(locations, since))
        return self._fetch_demo(locations, since)

    def _mark_demo(self, frames: list[IngestedFrame]) -> list[IngestedFrame]:
        for f in frames:
            f.is_synthetic = True
        return frames

    # -- subclasses --
    def _fetch_live(self, locations: list[dict], since: datetime | None) -> list[IngestedFrame]:
        raise NotImplementedError

    def _fetch_demo(self, locations: list[dict], since: datetime | None) -> list[IngestedFrame]:
        raise NotImplementedError


def _frame(location_id: str, metric: str, value: float, source_id: str,
           unit: str = "", at: datetime | None = None) -> IngestedFrame:
    return IngestedFrame(
        location_id=location_id, metric=metric, value=round(float(value), 3),
        source_id=source_id, unit=unit,
        captured_at=at or datetime.now(timezone.utc),
        is_synthetic=True,
    )


def _demo_derived(loc: dict, metric: str, base: float, jitter: float = 0.15) -> float:
    """Deterministic continuation from the zone's own telemetry (same-feature
    persistence) so demo frames look like a coherent live feed, not noise."""
    exposure = loc.get("exposure", 1.0)
    seed = sum(ord(c) for c in loc.get("id", "x"))
    wobble = (seed % 7) / 7.0 - 0.5
    return base * exposure * (1 + wobble * jitter)
