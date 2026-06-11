"""End-to-end + unit coverage for the stage gates.

Run from the repo root:  python -m pytest   (or)  python tests/test_framework.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wrodium.schema import (  # noqa: E402
    load_primitive, validate_primitive, load_golden, validate_golden,
    load_proposal, validate_proposal, Proposal,
)
from wrodium.adapters import (  # noqa: E402
    PerfectMockAdapter, FaultyMockAdapter, run_conformance, AdapterError, CallState,
)
from wrodium.scoring import score_cell, aggregate_vendor, fidelity, ResultState  # noqa: E402
from wrodium.snapshot import preflight, dry_run, run_snapshot, snapshot_id  # noqa: E402
from wrodium.publish import render_llms_txt, well_known_mcp, BenchRegistry  # noqa: E402

PRIM = ROOT / "primitives" / "web_extraction.yaml"
GOLD = ROOT / "golden" / "web_extraction" / "rows.sample.jsonl"


def _load():
    return load_primitive(PRIM), load_golden(GOLD)


# ---- Stage 2: primitive spec ------------------------------------------------

def test_canonical_primitive_validates():
    p, _ = _load()
    r = validate_primitive(p)
    assert r.passed, r.render()


def test_missing_cost_per_correct_is_error():
    p, _ = _load()
    p.metrics = [m for m in p.metrics if m.key != "cost_per_correct"]
    p.raw["metrics"] = [m for m in p.raw["metrics"] if m["key"] != "cost_per_correct"]
    r = validate_primitive(p)
    assert any(i.code == "metric.missing_cost_per_correct" for i in r.errors)


def test_pending_review_vendor_is_error():
    p, _ = _load()
    p.vendors[0].tos_status = "pending_review"
    r = validate_primitive(p)
    assert any(i.code == "vendor.tos_pending" for i in r.errors)


def test_metric_without_dash_semantics_is_error():
    p, _ = _load()
    p.metrics[0].dash_semantics = None
    r = validate_primitive(p)
    assert any(i.code == "metric.missing_dash_semantics" for i in r.errors)


# ---- Stage 0: proposal scorecard -------------------------------------------

def test_proposal_below_threshold_rejected():
    prop = Proposal(name="x", rationale="r", consumer_tasks=["t"],
                    scores={"deterministic_truth": True, "agents_are_buyers": True})
    assert not validate_proposal(prop).passed


def test_proposal_insiders_auto_reject():
    prop = Proposal(name="x", rationale="r", consumer_tasks=["t"],
                    scores={k: True for k in
                            ["deterministic_truth", "agents_are_buyers", "freshness_scoreable",
                             "four_plus_vendors", "wrodium_leverage"]},
                    truth_needs_insiders=True)
    r = validate_proposal(prop)
    assert any(i.code == "proposal.rejected_insiders" for i in r.errors)


# ---- Stage 3: golden --------------------------------------------------------

def test_golden_validates():
    p, g = _load()
    assert validate_golden(g, p).passed


def test_golden_holdout_floor():
    p, g = _load()
    for row in g:
        row.split = "public"            # 0% holdout
    r = validate_golden(g, p)
    assert any(i.code == "golden.holdout_too_small" for i in r.errors)


# ---- Stage 4: adapter contract ---------------------------------------------

def test_perfect_adapter_conformant():
    _, g = _load()
    truth = {row.id: row.golden for row in g}
    assert run_conformance(PerfectMockAdapter(truth)).passed


def test_undeclared_capability_raises():
    adapter = PerfectMockAdapter({})
    try:
        adapter.call("nope")
        assert False, "should have raised"
    except AdapterError:
        pass


def test_error_mapping_states():
    _, g = _load()
    truth = {row.id: row.golden for row in g}
    a = FaultyMockAdapter(truth, order=[r.id for r in g])
    states = {a.call("extract", row_id=r.id).state for r in g}
    assert CallState.BLOCKED in states and CallState.TIMEOUT in states and CallState.FETCH_FAILED in states


# ---- Stage 5: scoring + dry run --------------------------------------------

def test_perfect_vendor_fidelity_one():
    p, g = _load()
    fid, report = dry_run(p, g)
    assert fid == 1.0 and report.passed


def test_no_coverage_not_zero():
    p, g = _load()
    truth = {row.id: row.golden for row in g}
    a = PerfectMockAdapter({})            # returns empty -> no_coverage
    cells = [score_cell(a.call("extract", row_id=row.id), row.golden, scoring=p.scoring, row_id=row.id)
             for row in g]
    agg = aggregate_vendor(cells)
    assert all(c.state is ResultState.NO_COVERAGE for c in cells)
    assert agg.accuracy is None          # '-', never 0
    assert agg.cost_per_correct is None


# ---- Stage 6: snapshot + immutability --------------------------------------

def test_snapshot_runs_and_mints_id():
    p, g = _load()
    truth = {row.id: row.golden for row in g}
    adapters = {p.vendors[0].key: PerfectMockAdapter(truth, cost_table={"extract": 0.001})}
    out = run_snapshot(p, g, adapters)
    assert out.snapshot is not None
    assert out.snapshot.id.startswith("web_extraction-")
    agg = out.snapshot.vendors[p.vendors[0].key]
    assert agg["accuracy"] == 1.0
    assert agg["overfit_gap"] == 0.0


def test_preflight_blocks_pending_vendor():
    p, g = _load()
    p.vendors[0].tos_status = "pending_review"
    assert not preflight(p, g).passed


# ---- Stage 8: publish + launch gate ----------------------------------------

def test_llms_txt_cites_snapshot():
    p, g = _load()
    truth = {row.id: row.golden for row in g}
    out = run_snapshot(p, g, {p.vendors[0].key: PerfectMockAdapter(truth, cost_table={"extract": 0.001})})
    txt = render_llms_txt(p, out.snapshot)
    assert out.snapshot.id in txt
    assert "How to read '-'" in txt


def test_launch_gate_recommend_cites_snapshot():
    p, g = _load()
    truth = {row.id: row.golden for row in g}
    out = run_snapshot(p, g, {p.vendors[0].key: PerfectMockAdapter(truth, cost_table={"extract": 0.001})})
    reg = BenchRegistry()
    reg.add(p, out.snapshot)
    rec = reg.recommend(p.consumer_tasks[0])
    assert rec["snapshot_id"] == out.snapshot.id
    assert rec["recommendations"][0]["vendor"] == p.vendors[0].key


if __name__ == "__main__":
    import traceback
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS {name}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
