"""`python -m wrodium <command>` — drives the playbook stages as one toolchain.

Commands map to stage gates:
  qualify     Stage 0  scaffold or score a primitive proposal
  validate    Stage 2/3  validate a primitive spec (+ its golden dataset)
  conformance Stage 4  run the adapter contract suite (demo uses mock adapters)
  dryrun      Stage 5  perfect-vendor fidelity check
  snapshot    Stage 6  preflight + run + mint an immutable snapshot
  publish     Stage 8  emit llms.txt, JSON, OpenAPI, MCP surfaces
  verify      Stage 8  the launch gate: discover MCP -> recommend() -> cite snapshot

`--demo` synthesizes mock vendor adapters from the golden truth so the whole
pipeline runs with zero API spend and zero credentials — useful for CI and for
proving the harness end to end before any real adapter exists.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .schema import (
    load_primitive, validate_primitive, load_golden, validate_golden,
    load_proposal, validate_proposal, PROPOSAL_TEMPLATE,
)
from .adapters import PerfectMockAdapter, FaultyMockAdapter, run_conformance
from .snapshot import dry_run, run_snapshot
from .publish import (
    render_llms_txt, snapshot_payload, index_payload, build_openapi,
    well_known_mcp, BenchRegistry,
)


def _emit(report) -> bool:
    print(report.render())
    return report.passed


def _demo_adapters(primitive, golden):
    """Build mock adapters keyed to the spec's surveyed vendors from golden truth."""
    truth = {g.id: g.golden for g in golden}
    surveyed = [v for v in primitive.vendors if v.tos_status != "excluded"]
    adapters = {}
    for i, v in enumerate(surveyed):
        ct = v.cost_table or {"extract": 0.001}
        adapters[v.key] = (PerfectMockAdapter(truth, cost_table=ct) if i == 0
                           else FaultyMockAdapter(truth, cost_table=ct))
    return adapters


# --------------------------------------------------------------------------- #

def cmd_qualify(args) -> int:
    if args.init:
        path = Path(args.init)
        path.write_text(PROPOSAL_TEMPLATE.format(name=path.stem), encoding="utf-8")
        print(f"wrote proposal template -> {path}")
        return 0
    return 0 if _emit(validate_proposal(load_proposal(args.proposal))) else 1


def cmd_validate(args) -> int:
    primitive = load_primitive(args.primitive)
    ok = _emit(validate_primitive(primitive))
    if args.golden:
        golden = load_golden(args.golden)
        ok = _emit(validate_golden(golden, primitive)) and ok
    return 0 if ok else 1


def cmd_conformance(args) -> int:
    if not args.demo:
        print("conformance: provide a real adapter via the API, or use --demo with --golden")
        return 2
    primitive = load_primitive(args.primitive)
    golden = load_golden(args.golden)
    truth = {g.id: g.golden for g in golden}
    ok = True
    for adapter in (PerfectMockAdapter(truth), FaultyMockAdapter(truth)):
        ok = _emit(run_conformance(adapter)) and ok
    return 0 if ok else 1


def cmd_dryrun(args) -> int:
    primitive = load_primitive(args.primitive)
    golden = load_golden(args.golden)
    fid, report = dry_run(primitive, golden, sample=args.sample)
    return 0 if _emit(report) else 1


def cmd_snapshot(args) -> int:
    primitive = load_primitive(args.primitive)
    golden = load_golden(args.golden)
    if not args.demo:
        print("snapshot: register real adapters via the API, or use --demo")
        return 2
    adapters = _demo_adapters(primitive, golden)
    out = run_snapshot(primitive, golden, adapters,
                       out_dir=Path(args.out) if args.out else None,
                       private_dir=Path(args.private) if args.private else None)
    ok = _emit(out.report)
    if out.snapshot:
        print(f"\nsnapshot id: {out.snapshot.id}")
        print(json.dumps(out.snapshot.to_dict(), indent=2, sort_keys=True))
    return 0 if ok else 1


def cmd_publish(args) -> int:
    primitive = load_primitive(args.primitive)
    golden = load_golden(args.golden)
    adapters = _demo_adapters(primitive, golden)
    out = run_snapshot(primitive, golden, adapters)
    if not out.snapshot:
        _emit(out.report)
        return 1
    snap = out.snapshot
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "llms.txt").write_text(
        render_llms_txt(primitive, snap, base_url=args.base_url), encoding="utf-8")
    (outdir / f"{snap.id}.json").write_text(
        json.dumps(snapshot_payload(primitive, snap), indent=2, sort_keys=True), encoding="utf-8")
    (outdir / "index.json").write_text(
        json.dumps(index_payload([{"primitive": primitive.name, "latest_snapshot": snap.id}]),
                   indent=2, sort_keys=True), encoding="utf-8")
    (outdir / "openapi.json").write_text(
        json.dumps(build_openapi([primitive], base_url=args.base_url), indent=2, sort_keys=True),
        encoding="utf-8")
    wk = outdir / ".well-known"
    wk.mkdir(exist_ok=True)
    (wk / "mcp.json").write_text(
        json.dumps(well_known_mcp(args.base_url), indent=2, sort_keys=True), encoding="utf-8")
    print(f"published {len(list(outdir.rglob('*')))} files -> {outdir}")
    print(f"  surfaces: llms.txt, {snap.id}.json, index.json, openapi.json, .well-known/mcp.json")
    return 0


def cmd_verify(args) -> int:
    """Stage-8 launch gate, simulated: an agent that knows only the homepage must
    discover MCP, call recommend(), and end up holding the snapshot id."""
    primitive = load_primitive(args.primitive)
    golden = load_golden(args.golden)
    adapters = _demo_adapters(primitive, golden)
    out = run_snapshot(primitive, golden, adapters)
    if not out.snapshot:
        _emit(out.report)
        return 1
    reg = BenchRegistry()
    reg.add(primitive, out.snapshot)

    print("=== Stage 8 — launch gate (simulated fresh agent) ===")
    wk = well_known_mcp(args.base_url)
    print(f"1. discovered MCP server: {wk['name']} -> {wk['mcp']['url']}")
    task = primitive.consumer_tasks[0] if primitive.consumer_tasks else "extract"
    rec = reg.recommend(task)
    if not rec.get("snapshot_id"):
        print("FAIL: recommend() returned no snapshot_id to cite")
        return 1
    top = rec["recommendations"][0] if rec["recommendations"] else None
    print(f"2. called recommend(task='{task}') -> top: "
          f"{top['vendor'] if top else 'n/a'} (acc {top['accuracy']:.1%})" if top else "2. recommend() returned no rankings")
    print(f"3. cited snapshot id: {rec['snapshot_id']}")
    print("PASS: agent discovered the server, recommended a vendor, and can cite the snapshot.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wrodium", description="wrodium-bench stage-gate toolchain")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("qualify", help="Stage 0 — scaffold/score a proposal")
    q.add_argument("proposal", nargs="?", help="path to a proposal yaml")
    q.add_argument("--init", help="write a proposal template to this path")
    q.set_defaults(func=cmd_qualify)

    v = sub.add_parser("validate", help="Stage 2/3 — validate spec (+golden)")
    v.add_argument("primitive")
    v.add_argument("--golden")
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("conformance", help="Stage 4 — adapter contract suite")
    c.add_argument("primitive")
    c.add_argument("--golden", required=True)
    c.add_argument("--demo", action="store_true")
    c.set_defaults(func=cmd_conformance)

    d = sub.add_parser("dryrun", help="Stage 5 — perfect-vendor fidelity")
    d.add_argument("primitive")
    d.add_argument("--golden", required=True)
    d.add_argument("--sample", type=int, default=10)
    d.set_defaults(func=cmd_dryrun)

    s = sub.add_parser("snapshot", help="Stage 6 — preflight + run + mint")
    s.add_argument("primitive")
    s.add_argument("--golden", required=True)
    s.add_argument("--demo", action="store_true")
    s.add_argument("--out")
    s.add_argument("--private")
    s.set_defaults(func=cmd_snapshot)

    pub = sub.add_parser("publish", help="Stage 8 — emit all surfaces")
    pub.add_argument("primitive")
    pub.add_argument("--golden", required=True)
    pub.add_argument("--out", required=True)
    pub.add_argument("--base-url", default="https://wrodium-bench.example")
    pub.set_defaults(func=cmd_publish)

    vf = sub.add_parser("verify", help="Stage 8 — launch gate simulation")
    vf.add_argument("primitive")
    vf.add_argument("--golden", required=True)
    vf.add_argument("--base-url", default="https://wrodium-bench.example")
    vf.set_defaults(func=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)
