"""llms.txt renderer (Stage 8): the full leaderboard as agent-readable markdown.

The playbook's launch gate says the agent is the customer; this file is the primary
machine surface. It renders the snapshot aggregates verbatim, the per-metric dash
semantics (so an agent never misreads '-' as 0), exclusions with reasons, and the
snapshot id an agent must be able to cite.
"""
from __future__ import annotations

from ..schema.primitive import Primitive
from ..snapshot.run import Snapshot


def _fmt(metric, value) -> str:
    if value is None:
        return "-"   # dash semantics are documented in the legend below
    if isinstance(value, float):
        if metric in ("accuracy", "coverage"):
            return f"{value:.1%}"
        if metric == "cost_per_correct":
            return f"${value:.4f}"
        return f"{value:.3f}"
    return str(value)


def render_llms_txt(primitive: Primitive, snapshot: Snapshot, *, base_url: str = "https://wrodium-bench.example") -> str:
    cols = ["accuracy", "coverage", "cost_per_correct", "overfit_gap"]
    lines: list[str] = []
    lines.append(f"# wrodium-bench — {primitive.name}")
    lines.append("")
    lines.append(f"> Snapshot `{snapshot.id}` · immutable · cohort {snapshot.cohort_size} rows · "
                 f"consumer tasks: {', '.join(primitive.consumer_tasks) or 'n/a'}")
    lines.append("")
    lines.append(f"License: CC-BY-4.0 · Independence: vendor-funded benchmarks are disclosed on the human page.")
    lines.append(f"MCP: {base_url}/.well-known/mcp.json · JSON: {base_url}/api/{primitive.name}/{snapshot.id}.json")
    lines.append("")

    # Leaderboard table.
    header = "| vendor | " + " | ".join(cols) + " | ToS |"
    sep = "|" + "---|" * (len(cols) + 2)
    lines += ["## Leaderboard", "", header, sep]
    for vkey, agg in sorted(snapshot.vendors.items(),
                            key=lambda kv: (kv[1].get("accuracy") is None, -(kv[1].get("accuracy") or 0))):
        row = [vkey] + [_fmt(c, agg.get(c)) for c in cols] + [agg.get("tos_status", "?")]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Dash legend — Rule 2 made visible to the agent.
    lines += ["## How to read '-'", ""]
    for m in primitive.metrics:
        if m.dash_semantics:
            lines.append(f"- **{m.key}**: `-` means {m.dash_semantics}")
    lines.append("")

    # Exclusions — the 'not surveyed' honesty pattern.
    excluded = [v for v in primitive.vendors if v.tos_status == "excluded"]
    if excluded:
        lines += ["## Not surveyed", ""]
        for v in excluded:
            lines.append(f"- **{v.key}**: {v.exclusion_reason or 'excluded'}")
        lines.append("")

    lines += ["## Methodology", "",
              f"Scoring is deterministic; every rule is published verbatim at {base_url}/{primitive.name}/methodology.",
              f"Cite this snapshot as `{snapshot.id}`.", ""]
    return "\n".join(lines)
