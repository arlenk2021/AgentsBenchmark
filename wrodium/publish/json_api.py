"""JSON API payloads (Stage 8).

Pure data builders — no web framework assumed. A thin server (FastAPI/Flask/Vercel
function) imports these and serves the dicts at the documented routes. The OpenAPI
spec in `openapi.py` describes exactly these shapes.
"""
from __future__ import annotations

from ..schema.primitive import Primitive
from ..snapshot.run import Snapshot


def snapshot_payload(primitive: Primitive, snapshot: Snapshot) -> dict:
    """GET /api/{primitive}/{snapshot_id}.json — the immutable aggregate."""
    return {
        "snapshot_id": snapshot.id,
        "primitive": primitive.name,
        "consumer_tasks": primitive.consumer_tasks,
        "cohort_size": snapshot.cohort_size,
        "content_hash": snapshot.content_hash,
        "license": "CC-BY-4.0",
        "metrics": [
            {"key": m.key, "direction": m.direction, "unit": m.unit,
             "dash_semantics": m.dash_semantics, "description": m.description}
            for m in primitive.metrics
        ],
        "vendors": snapshot.vendors,
        "exclusions": [
            {"vendor": v.key, "reason": v.exclusion_reason}
            for v in primitive.vendors if v.tos_status == "excluded"
        ],
    }


def index_payload(entries: list[dict]) -> dict:
    """GET /api/index.json — every primitive and its latest snapshot id."""
    return {"benchmarks": entries, "license": "CC-BY-4.0"}
