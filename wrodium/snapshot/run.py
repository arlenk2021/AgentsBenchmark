"""Snapshot runner (Stages 5-6): dry run, full run, immutable snapshot minting.

Order of operations mirrors the playbook:
  * `dry_run()` scores a mocked perfect vendor and asserts fidelity 1.0 (Stage-3
    exit / Stage-5 dry run) — fails fast on schema/scorer mismatch before spend.
  * `run_snapshot()` runs preflight, executes every (vendor, row) cell, aggregates,
    computes overfit_gap, and mints an immutable snapshot id `<primitive>-<year>-q<N>`.

A minted snapshot is immutable forever: re-minting the same id with different
content raises. Raw responses are partitioned public-split -> repo artifact,
holdout -> private path.
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..adapters.base import VendorAdapter
from ..adapters.mock import PerfectMockAdapter
from ..schema.primitive import Primitive
from ..schema.golden import GoldenRow
from ..scoring.engine import score_cell, CellScore
from ..scoring.metrics import aggregate_vendor, fidelity, overfit_gap
from ..util import Report, stable_hash
from .preflight import preflight


def _capability(primitive: Primitive) -> str:
    cap = primitive.scoring.get("capability")
    if cap:
        return cap
    shapes = primitive.task_shapes
    if shapes:
        first = shapes[0]
        return first.get("capability", first.get("name")) if isinstance(first, dict) else str(first)
    return "extract"


def snapshot_id(primitive: Primitive, on: Optional[_dt.date] = None) -> str:
    on = on or _dt.date.today()
    quarter = (on.month - 1) // 3 + 1
    return f"{primitive.name}-{on.year}-q{quarter}"


def _score_rows(adapter: VendorAdapter, rows: list[GoldenRow], primitive: Primitive) -> list[CellScore]:
    cap = _capability(primitive)
    out: list[CellScore] = []
    for row in rows:
        result = adapter.call(cap, row_id=row.id, region=row.region, **row.raw.get("input", {}))
        out.append(score_cell(result, row.golden, scoring=primitive.scoring, row_id=row.id))
    return out


# --------------------------------------------------------------------------- #

def dry_run(primitive: Primitive, golden: list[GoldenRow], *, sample: int = 10) -> tuple[float, Report]:
    """Score a mocked perfect vendor on a small slice; fidelity must be 1.0."""
    r = Report(stage="Stage 5 — dry run (perfect vendor)")
    rows = golden[:sample]
    truth = {row.id: row.golden for row in rows}
    adapter = PerfectMockAdapter(truth)
    cells = _score_rows(adapter, rows, primitive)
    fid = fidelity(cells)
    if abs(fid - 1.0) > 1e-9:
        misses = [c.row_id for c in cells if c.state.value != "correct"]
        r.error("dryrun.fidelity_not_one",
                f"perfect vendor scored fidelity {fid:.3f} (expected 1.0); "
                f"schema/scorer mismatch on rows {misses}", primitive.name)
    else:
        r.info("dryrun.ok", f"perfect vendor fidelity 1.0 over {len(rows)} rows", primitive.name)
    return fid, r


@dataclass
class Snapshot:
    id: str
    primitive: str
    minted_for: str                         # date string the id was derived from
    vendors: dict[str, dict] = field(default_factory=dict)   # vendor -> aggregate + overfit
    cohort_size: int = 0
    content_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.id, "primitive": self.primitive,
            "minted_for": self.minted_for, "cohort_size": self.cohort_size,
            "vendors": self.vendors, "content_hash": self.content_hash,
        }


@dataclass
class RunOutcome:
    report: Report
    snapshot: Optional[Snapshot] = None
    cells: dict[str, list[CellScore]] = field(default_factory=dict)


def run_snapshot(
    primitive: Primitive,
    golden: list[GoldenRow],
    adapters: dict[str, VendorAdapter],
    *,
    on: Optional[_dt.date] = None,
    out_dir: Optional[Path] = None,
    private_dir: Optional[Path] = None,
) -> RunOutcome:
    report = Report(stage="Stage 6 — snapshot run")

    # 1. Hard preflight. No spend on a failing spec/golden/ToS.
    pf = preflight(primitive, golden)
    report.extend(pf)
    if not pf.passed:
        report.error("snapshot.preflight_failed", "preflight gate failed; aborting run", primitive.name)
        return RunOutcome(report=report)

    public = [g for g in golden if g.split == "public"]
    holdout = [g for g in golden if g.split == "holdout"]

    sid = snapshot_id(primitive, on)
    snap = Snapshot(id=sid, primitive=primitive.name,
                    minted_for=str(on or _dt.date.today()), cohort_size=len(golden))
    all_cells: dict[str, list[CellScore]] = {}
    raw_public: list[dict] = []
    raw_holdout: list[dict] = []

    for vkey, adapter in adapters.items():
        if primitive.vendor(vkey) is None:
            report.warn("snapshot.unknown_adapter", f"adapter '{vkey}' has no vendor row in the spec", vkey)
        pub_cells = _score_rows(adapter, public, primitive)
        raw_public.extend(adapter.drain_raw_log())
        hold_cells = _score_rows(adapter, holdout, primitive)
        raw_holdout.extend(adapter.drain_raw_log())

        all_cells[vkey] = pub_cells + hold_cells
        agg = aggregate_vendor(all_cells[vkey])
        snap.vendors[vkey] = {
            **agg.to_dict(),
            "overfit_gap": overfit_gap(pub_cells, hold_cells),
            "public_accuracy": aggregate_vendor(pub_cells).accuracy,
            "holdout_accuracy": aggregate_vendor(hold_cells).accuracy,
            "tos_status": primitive.vendor(vkey).tos_status if primitive.vendor(vkey) else "unknown",
        }

    # Immutable content hash over the scored aggregates (not raw, not timing).
    snap.content_hash = stable_hash({k: {kk: vv for kk, vv in v.items()
                                         if kk not in ("mean_latency_ms",)}
                                     for k, v in snap.vendors.items()})

    if out_dir is not None:
        _persist(snap, raw_public, raw_holdout, out_dir, private_dir, report)

    report.info("snapshot.minted",
                f"{sid} :: {len(adapters)} vendors over {len(golden)} rows "
                f"(public {len(public)}, holdout {len(holdout)})", primitive.name)
    return RunOutcome(report=report, snapshot=snap, cells=all_cells)


def _persist(snap: Snapshot, raw_public: list[dict], raw_holdout: list[dict],
             out_dir: Path, private_dir: Optional[Path], report: Report) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{snap.id}.json"

    # Immutability: a minted snapshot id may never change content.
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("content_hash") != snap.content_hash:
            raise RuntimeError(
                f"snapshot {snap.id} already exists with a different content hash — "
                "snapshots are immutable forever; mint a new id (re-run quarter)"
            )
        report.info("snapshot.idempotent", f"{snap.id} already minted with identical content", snap.id)
        return

    target.write_text(json.dumps(snap.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    # Public-split raw -> repo artifact; holdout raw -> private only (dataset never leaves).
    (out_dir / f"{snap.id}.raw.public.jsonl").write_text(
        "\n".join(json.dumps(x, default=str) for x in raw_public) + "\n", encoding="utf-8")
    if private_dir is not None:
        pdir = Path(private_dir)
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / f"{snap.id}.raw.holdout.jsonl").write_text(
            "\n".join(json.dumps(x, default=str) for x in raw_holdout) + "\n", encoding="utf-8")
    report.info("snapshot.persisted", f"wrote {target.name} (+ raw artifacts)", snap.id)
