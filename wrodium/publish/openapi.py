"""OpenAPI 3.1 spec generator (Stage 8 checklist item).

Describes the JSON routes in `json_api.py`. Kept minimal but valid 3.1 so an agent
toolchain can ingest it directly.
"""
from __future__ import annotations

from ..schema.primitive import Primitive


def build_openapi(primitives: list[Primitive], *, base_url: str = "https://wrodium-bench.example") -> dict:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "wrodium-bench API",
            "version": "1.0.0",
            "description": "Agent-consumable vendor leaderboards. Immutable snapshots, "
                           "deterministic scoring, CC-BY-4.0.",
            "license": {"name": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/api/index.json": {
                "get": {
                    "operationId": "listBenchmarks",
                    "summary": "List all primitives and their latest snapshot ids.",
                    "responses": {"200": {"description": "ok", "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Index"}}}}},
                }
            },
            "/api/{primitive}/{snapshotId}.json": {
                "get": {
                    "operationId": "getSnapshot",
                    "summary": "Fetch an immutable snapshot's aggregates.",
                    "parameters": [
                        {"name": "primitive", "in": "path", "required": True,
                         "schema": {"type": "string", "enum": [p.name for p in primitives]}},
                        {"name": "snapshotId", "in": "path", "required": True,
                         "schema": {"type": "string", "pattern": r"^[a-z0-9_]+-\d{4}-q[1-4]$"}},
                    ],
                    "responses": {"200": {"description": "ok", "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Snapshot"}}}}},
                }
            },
        },
        "components": {"schemas": {
            "Index": {"type": "object", "properties": {
                "benchmarks": {"type": "array", "items": {"type": "object"}},
                "license": {"type": "string"}}},
            "Snapshot": {"type": "object", "required": ["snapshot_id", "primitive", "vendors"],
                "properties": {
                    "snapshot_id": {"type": "string"},
                    "primitive": {"type": "string"},
                    "cohort_size": {"type": "integer"},
                    "content_hash": {"type": "string"},
                    "vendors": {"type": "object", "additionalProperties": {
                        "type": "object", "properties": {
                            "accuracy": {"type": ["number", "null"]},
                            "coverage": {"type": ["number", "null"]},
                            "cost_per_correct": {"type": ["number", "null"]},
                            "overfit_gap": {"type": ["number", "null"]}}}}}},
        }},
    }
