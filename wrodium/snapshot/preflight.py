"""Snapshot preflight — the hard gate (Stage 6).

The playbook promises this is "already enforced in snapshot/run.py": a snapshot run
refuses to start unless ToS gates pass, cost tables are non-null, and holdout >= 25%.
This module composes the upstream validators plus the run-time-only checks, so the
gate is a single call with one verdict.
"""
from __future__ import annotations

from ..schema.primitive import Primitive, validate_primitive, PUBLISHABLE_TOS
from ..schema.golden import GoldenRow, validate_golden
from ..util import Report


def preflight(primitive: Primitive, golden: list[GoldenRow]) -> Report:
    r = Report(stage="Stage 6 — snapshot preflight")

    # Re-run the spec and golden validators — nothing runs on a spec that itself fails.
    r.extend(validate_primitive(primitive))
    r.extend(validate_golden(golden, primitive))

    # ToS gate: every surveyed vendor must be cleared/static_rubric_only, and any
    # excluded vendor must carry a public reason. pending_review hard-fails.
    surveyed = [v for v in primitive.vendors if v.tos_status != "excluded"]
    if not surveyed:
        r.error("preflight.no_surveyed_vendors", "no vendors left to survey after exclusions", primitive.name)
    for v in primitive.vendors:
        if v.tos_status == "pending_review":
            r.error("preflight.tos_pending", f"vendor '{v.key}' still pending_review", primitive.name)
        if v.tos_status in PUBLISHABLE_TOS and not v.cost_table:
            r.error("preflight.cost_table_null",
                    f"vendor '{v.key}' has a null cost table — cost tables must be non-null", primitive.name)

    # Holdout >= 25% (also checked in validate_golden; asserted here as the gate's own line).
    n = len(golden)
    holdout = sum(1 for g in golden if g.split == "holdout")
    if n and holdout / n < 0.25:
        r.error("preflight.holdout_too_small",
                f"holdout {holdout}/{n} ({holdout/n:.0%}) < 25%", primitive.name)

    if r.passed:
        r.info("preflight.cleared",
               f"cleared: {len(surveyed)} vendors, {n} rows, holdout {holdout}", primitive.name)
    return r
