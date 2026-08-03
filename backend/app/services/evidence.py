"""Evidence ledger — every risk score is traceable to sources with provenance."""

from __future__ import annotations

from app.core import models


def make_evidence(
    db,
    prediction_id: int | None,
    source: models.Source,
    kind: str,
    captured_at,
    description: str,
    value: float | None = None,
    payload: dict | None = None,
) -> models.EvidenceObject:
    obj = models.EvidenceObject(
        id=f"ev_{prediction_id}_{kind}_{abs(hash((kind, description, str(captured_at)))) % 10**9}",
        prediction_id=prediction_id,
        source_id=source.id,
        kind=kind,
        captured_at=captured_at,
        description=description,
        value=value,
        payload=payload or {},
    )
    db.add(obj)
    return obj


def to_schema(ev: models.EvidenceObject, source: models.Source) -> dict:
    return {
        "id": ev.id,
        "kind": ev.kind,
        "captured_at": ev.captured_at,
        "description": ev.description,
        "value": ev.value,
        "payload": ev.payload or {},
        "provenance": {
            "source_id": source.id,
            "source_name": source.name,
            "kind": source.kind,
            "url": source.url,
            "is_synthetic": source.is_synthetic,
        },
    }
