"""NASA GPM / Copernicus satellite precipitation & soil-moisture adapter.

Live: `GET {endpoint}/precip?bbox=...` or a per-station product; demo keeps the
zone's soil-moisture anomaly coherent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.services.ingest.base import DataSourceAdapter, _demo_derived, _frame

DEMO_SOURCE = "gpm-nasa"
API_SOURCE = "gpm-nasa-live"


class GPMAdapter(DataSourceAdapter):
    id = "gpm"
    kind = "satellite"
    description = (
        "NASA GPM/IMERG 30-min precipitation + soil-moisture proxy. Live when GPM_ENDPOINT is set; else labeled demo."
    )
    endpoint_attr = "gpm_endpoint"
    token_attr = "gpm_token"

    def _fetch_live(self, locations, since=None):
        url = f"{self.endpoint.rstrip('/')}/precip"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        frames = []
        with httpx.Client(timeout=8) as client:
            for loc in locations:
                r = client.get(url, params={"lat": loc["lat"], "lon": loc["lon"]}, headers=headers)
                r.raise_for_status()
                for row in r.json().get("frames", []):
                    frames.append(
                        _frame(
                            loc["id"],
                            "soil_moisture_anomaly",
                            row["soil_moisture_anomaly"],
                            API_SOURCE,
                            unit="sigma",
                            at=datetime.fromisoformat(row["ts"]),
                        )
                    )
        return frames

    def _fetch_demo(self, locations, since=None):
        frames = []
        now = since or datetime.now(timezone.utc)
        for loc in locations:
            frames.append(
                _frame(
                    loc["id"],
                    "soil_moisture_anomaly",
                    _demo_derived(loc, "soil_moisture", 3.0),
                    DEMO_SOURCE,
                    unit="sigma",
                    at=now,
                )
            )
        return frames
