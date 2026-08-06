"""India Meteorological Department rainfall adapter.

Live: `GET {endpoint}/rainfall?station={location_id}&hours=24` → [{ts, rain_mm, ...}]
Demo: deterministic continuation from each zone's seeded rain profile.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.services.ingest.base import DataSourceAdapter, _demo_derived, _frame

DEMO_SOURCE = "imd-rain"
API_SOURCE = "imd-rain-live"


class IMDAdapter(DataSourceAdapter):
    id = "imd"
    kind = "weather"
    description = (
        "IMD rainfall — hourly accumulation per monitored zone. Live when IMD_ENDPOINT is set; else labeled demo."
    )
    endpoint_attr = "imd_endpoint"
    token_attr = "imd_token"

    def _fetch_live(self, locations, since=None):
        url = f"{self.endpoint.rstrip('/')}/rainfall"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        frames = []
        with httpx.Client(timeout=8) as client:
            for loc in locations:
                r = client.get(url, params={"station": loc["id"], "hours": 24}, headers=headers)
                r.raise_for_status()
                for row in r.json().get("readings", []):
                    frames.append(
                        _frame(
                            loc["id"],
                            "rainfall_mm",
                            row["rain_mm"],
                            API_SOURCE,
                            unit="mm",
                            at=datetime.fromisoformat(row["ts"]),
                        )
                    )
        return frames

    def _fetch_demo(self, locations, since=None):
        frames = []
        now = since or datetime.now(timezone.utc)
        for loc in locations:
            frames.append(
                _frame(loc["id"], "rainfall_mm", _demo_derived(loc, "rainfall_mm", 4.0), DEMO_SOURCE, unit="mm", at=now)
            )
        return frames
