"""Tamil Nadu reservoir (PWD/WRD) storage & release adapter.

Live: `GET {endpoint}/reservoirs?district={region}` → storage/level/inflow per dam.
These frames do not feed the canonical feature tables yet — they land in the
IngestedDatum archive and surface as provenance + release-impact context.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.services.ingest.base import DataSourceAdapter, _demo_derived, _frame

DEMO_SOURCE = "cwprs-level"
API_SOURCE = "wrd-release-live"


class ReservoirAdapter(DataSourceAdapter):
    id = "reservoir"
    kind = "water"
    description = (
        "Tamil Nadu PWD/WRD reservoir storage, level and release. "
        "Live when RESERVOIR_ENDPOINT is set; else labeled demo."
    )
    endpoint_attr = "reservoir_endpoint"
    token_attr = "reservoir_token"

    def _fetch_live(self, locations, since=None):
        url = f"{self.endpoint.rstrip('/')}/reservoirs"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        frames = []
        with httpx.Client(timeout=8) as client:
            for loc in locations:
                r = client.get(url, params={"district": loc.get("region", "")}, headers=headers)
                r.raise_for_status()
                for row in r.json().get("dams", []):
                    frames.append(
                        _frame(
                            loc["id"],
                            "reservoir_storage_pct",
                            row["storage_pct"],
                            API_SOURCE,
                            unit="%",
                            at=datetime.fromisoformat(row["ts"]),
                        )
                    )
                    frames.append(
                        _frame(
                            loc["id"],
                            "reservoir_release_m3s",
                            row.get("release_m3s", 0),
                            API_SOURCE,
                            unit="m3/s",
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
                    "reservoir_storage_pct",
                    _demo_derived(loc, "storage_pct", 82.0),
                    DEMO_SOURCE,
                    unit="%",
                    at=now,
                )
            )
            frames.append(
                _frame(
                    loc["id"],
                    "reservoir_release_m3s",
                    _demo_derived(loc, "release_m3s", 45.0),
                    DEMO_SOURCE,
                    unit="m3/s",
                    at=now,
                )
            )
        return frames
