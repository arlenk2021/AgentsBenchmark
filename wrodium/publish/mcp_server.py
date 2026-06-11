"""MCP surface (Stage 8) — the customer-facing API, since the agent is the customer.

The playbook's launch gate (a hard ship-blocker) is: a fresh Claude Code session,
given only the homepage URL, must discover the MCP server, call `recommend()`, and
cite the snapshot id — unaided. So this module provides:
  * `well_known_mcp()` — the /.well-known/mcp.json discovery document,
  * `TOOLS` — recommend()/query() tool descriptors with JSON-Schema inputs,
  * `BenchRegistry` — a transport-agnostic implementation an MCP server wraps.

The recommend() result ALWAYS carries `snapshot_id` so the agent can cite it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..schema.primitive import Primitive
from ..snapshot.run import Snapshot


def well_known_mcp(base_url: str = "https://wrodium-bench.example") -> dict:
    return {
        "schema_version": "2025-06-01",
        "name": "wrodium-bench",
        "description": "Vendor leaderboards for agentic consumers — pick the best API "
                       "for a task, by accuracy per dollar, from immutable snapshots.",
        "mcp": {"transport": "streamable-http", "url": f"{base_url}/mcp"},
        "documentation": f"{base_url}/llms.txt",
        "tools": [t["name"] for t in TOOLS],
        "license": "CC-BY-4.0",
    }


TOOLS = [
    {
        "name": "recommend",
        "description": "Recommend the best vendor(s) for a consumer task, ranked by accuracy "
                       "per dollar. Returns the citing snapshot_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "consumer task, e.g. 'page_extraction'"},
                "region": {"type": "string"},
                "budget_priority": {"type": "string", "enum": ["accuracy", "cost", "balanced"],
                                    "default": "balanced"},
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["task"],
        },
    },
    {
        "name": "query",
        "description": "Return the raw aggregate row(s) for a primitive, optionally one vendor.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "primitive": {"type": "string"},
                "vendor": {"type": "string"},
            },
            "required": ["primitive"],
        },
    },
]


@dataclass
class _Entry:
    primitive: Primitive
    snapshot: Snapshot


@dataclass
class BenchRegistry:
    """Holds the published primitives+snapshots and answers the MCP tools.
    A real server (FastMCP, etc.) registers `recommend`/`query` to call these."""
    entries: dict[str, _Entry] = field(default_factory=dict)

    def add(self, primitive: Primitive, snapshot: Snapshot) -> None:
        self.entries[primitive.name] = _Entry(primitive, snapshot)

    def _for_task(self, task: str) -> list[_Entry]:
        hits = [e for e in self.entries.values() if task in e.primitive.consumer_tasks]
        return hits or list(self.entries.values())

    def recommend(self, task: str, *, region: Optional[str] = None,
                  budget_priority: str = "balanced", top_k: int = 3) -> dict:
        candidates: list[dict] = []
        cited: list[str] = []
        for e in self._for_task(task):
            cited.append(e.snapshot.id)
            for vkey, agg in e.snapshot.vendors.items():
                if agg.get("tos_status") == "excluded":
                    continue
                acc, cpc = agg.get("accuracy"), agg.get("cost_per_correct")
                if acc is None:
                    continue  # no coverage -> not recommendable; never treated as 0
                score = _rank_score(acc, agg.get("coverage"), cpc, budget_priority)
                candidates.append({
                    "vendor": vkey, "primitive": e.primitive.name,
                    "accuracy": acc, "cost_per_correct": cpc,
                    "coverage": agg.get("coverage"), "rank_score": score,
                    "snapshot_id": e.snapshot.id,
                })
        candidates.sort(key=lambda c: c["rank_score"], reverse=True)
        ranked = candidates[:top_k]
        return {
            "task": task, "region": region, "budget_priority": budget_priority,
            "recommendations": ranked,
            "snapshot_id": ranked[0]["snapshot_id"] if ranked else (cited[0] if cited else None),
            "cited_snapshots": sorted(set(cited)),
            "note": "Ranked by accuracy per dollar from immutable wrodium-bench snapshots; "
                    "cite the snapshot_id.",
        }

    def query(self, primitive: str, *, vendor: Optional[str] = None) -> dict:
        e = self.entries.get(primitive)
        if not e:
            return {"error": f"unknown primitive '{primitive}'",
                    "available": sorted(self.entries)}
        if vendor:
            return {"snapshot_id": e.snapshot.id, "primitive": primitive,
                    "vendor": vendor, "aggregate": e.snapshot.vendors.get(vendor)}
        return {"snapshot_id": e.snapshot.id, "primitive": primitive,
                "vendors": e.snapshot.vendors}


def _rank_score(accuracy: float, coverage: Optional[float],
                cost_per_correct: Optional[float], priority: str) -> float:
    """Rank by realized quality per dollar.

    Quality is accuracy weighted by coverage (`accuracy * coverage`) so a vendor
    that is right whenever it answers but usually returns nothing does not outrank
    a full-coverage vendor — the agent cares about answers it actually gets.
      * accuracy: quality only;  * cost: cheapest per correct answer;
      * balanced (default): quality discounted by cost.
    """
    quality = accuracy * (coverage if coverage is not None else 1.0)
    if priority == "accuracy":
        return quality
    if cost_per_correct in (None, 0):
        return quality                 # free or unpriced -> rank on quality alone
    if priority == "cost":
        return 1.0 / cost_per_correct
    return quality / (1.0 + cost_per_correct)
