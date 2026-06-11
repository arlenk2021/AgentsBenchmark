# wrodium-bench

**The system behind the playbook.** The companion document
[`benchmark-creation-playbook.md`](benchmark-creation-playbook.md) describes the
*process* for shipping an agent-consumable vendor leaderboard. This repo is the
*machinery* that makes each of the playbook's stage gates mechanical instead of
manual: every "checklist" becomes a validator that returns a `Report`, and nothing
advances while a gate has an ERROR.

```
proposal ──▶ primitive spec ──▶ golden dataset ──▶ adapters ──▶ snapshot ──▶ surfaces
 Stage 0       Stage 2            Stage 3            Stage 4      Stage 5-6     Stage 8
qualify       validate           validate           conformance  dryrun/snap   publish/verify
```

The whole pipeline runs today with **zero API spend and zero credentials** via
`--demo`, which synthesizes mock vendor adapters from the golden truth. That's how
the harness proves itself before a single real adapter exists.

## Quickstart

```bash
cd wrodium-bench
python -m pytest                       # 17 gate tests, all green

P=primitives/web_extraction.yaml
G=golden/web_extraction/rows.sample.jsonl

python -m wrodium qualify primitives/_proposals/kyb_registry.example.yaml   # Stage 0
python -m wrodium validate    $P --golden $G                                # Stage 2 + 3
python -m wrodium conformance $P --golden $G --demo                         # Stage 4
python -m wrodium dryrun      $P --golden $G                                # Stage 5 (fidelity 1.0)
python -m wrodium snapshot    $P --golden $G --demo --out dist/snapshots    # Stage 6 (mint id)
python -m wrodium publish     $P --golden $G --out dist/site                # Stage 8 (all surfaces)
python -m wrodium verify      $P --golden $G                                # Stage 8 launch gate
```

## How each playbook stage is enforced in code

| Stage | Playbook gate | Enforced by | Hard ERRORs it raises |
|---|---|---|---|
| 0 Qualify | ≥3/5 scorecard; insiders → reject | `schema/proposal.py` | below threshold; insider-truth reject |
| 1 Legal/ToS | no vendor `pending_review`; pinned plan; exclusion reasons | `schema/primitive.py` + `snapshot/preflight.py` | `vendor.tos_pending`, `vendor.no_pinned_plan`, `vendor.no_exclusion_reason` |
| 2 Spec | required blocks; the three rules | `schema/primitive.py` | `metric.missing_cost_per_correct`, `metric.missing_dash_semantics`, strata/split checks |
| 3 Golden | every field verified; holdout ≥25%; stratified | `schema/golden.py` | `row.unverified`, `golden.holdout_too_small` |
| 4 Adapters | transport-only contract; undeclared raises; cost non-null; raw persisted | `adapters/base.py` + `adapters/conformance.py` | `adapter.undeclared_no_raise`, `adapter.missing_cost`, `adapter.raw_not_persisted` |
| 5 Scoring | deterministic functions; dry-run fidelity 1.0 | `scoring/engine.py` + `snapshot/run.py:dry_run` | `dryrun.fidelity_not_one` |
| 6 Snapshot | preflight gates; immutable id; overfit_gap | `snapshot/preflight.py` + `snapshot/run.py` | preflight failures; immutability `RuntimeError` |
| 8 Publish | llms.txt / JSON / OpenAPI / MCP; agent can cite snapshot | `publish/*` | launch gate fails if `recommend()` returns no `snapshot_id` |

## The three rules, made structural

The playbook calls out three rules that "prevent later pain." Here they are not
advice — they are conditions the code refuses to skip:

1. **Strata are difficulty axes, not topics.** Each stratum should declare what it
   `separates`; the validator warns when it doesn't.
2. **Every metric decides its `-` semantics.** `dash_semantics` is a required field;
   "no coverage" is carried as `None` through `scoring/metrics.py` and rendered `-`,
   never `0`.
3. **`cost_per_correct` is mandatory.** Its absence is a hard ERROR — agents buy
   accuracy per dollar, so a primitive without it cannot publish.

## Design invariants

- **Adapters transport, they never normalize meaning.** Any cleanup that changes a
  score lives in `scoring/`, where it is public and applied uniformly. `VendorAdapter`
  owns timing, raw persistence, and error mapping so it's identical across vendors;
  subclasses only implement `capabilities()` and `_invoke()`.
- **Reports gate stages.** A `Report` passes only with zero ERROR issues. Codes are
  stable and greppable (`metric.missing_cost_per_correct`), so failures are diagnosable.
- **Snapshots are immutable.** A minted id (`<primitive>-<year>-q<N>`) may never change
  content; re-minting with different aggregates raises.
- **The agent is the customer.** The launch gate (`wrodium verify`) simulates a fresh
  agent discovering `.well-known/mcp.json`, calling `recommend()`, and citing the
  snapshot id — the same hard gate the playbook ships behind.

See [`STRUCTURE.md`](STRUCTURE.md) for the file-by-file map.
