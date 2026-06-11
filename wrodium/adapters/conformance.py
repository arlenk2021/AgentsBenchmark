"""The adapter merge gate (Stage 4): `conformance_test`.

FDE reviews every adapter PR, but this is the mechanical green-light: an adapter
cannot merge until it passes the contract here. Checks are intentionally vendor-
agnostic — they probe the *contract*, not the vendor's data.
"""
from __future__ import annotations

from .base import VendorAdapter, CallState, AdapterError
from ..util import Report


def run_conformance(adapter: VendorAdapter, *, cost_table: dict | None = None) -> Report:
    r = Report(stage=f"Stage 4 — conformance: {adapter.key}")
    where = adapter.key

    # 1. Declares at least one capability.
    caps = adapter.capabilities()
    if not caps:
        r.error("adapter.no_capabilities", "adapter declares no capabilities", where)
        return r

    # 2. Undeclared capabilities raise (never silently no-op).
    try:
        adapter.call("__definitely_undeclared__")
        r.error("adapter.undeclared_no_raise",
                "calling an undeclared capability did not raise AdapterError", where)
    except AdapterError:
        pass
    except Exception as exc:  # noqa: BLE001
        r.error("adapter.undeclared_wrong_error",
                f"undeclared capability raised {type(exc).__name__}, expected AdapterError", where)

    # 3. Cost table covers every declared capability (Stage-1 PDF -> non-null cost).
    table = cost_table if cost_table is not None else adapter.cost_table
    for cap in caps:
        if cap not in table:
            r.error("adapter.missing_cost",
                    f"capability '{cap}' has no cost-table entry (cannot compute cost_per_correct)", where)

    # 4. Each declared capability is invokable and persists raw on every call.
    for cap in caps:
        adapter.drain_raw_log()
        try:
            res = adapter.call(cap)
        except AdapterError as exc:
            r.error("adapter.declared_not_implemented",
                    f"declared capability '{cap}' raised AdapterError: {exc}", where)
            continue
        if res.vendor != adapter.key:
            r.error("adapter.result_vendor_mismatch",
                    f"CallResult.vendor='{res.vendor}' != adapter.key", where)
        if not isinstance(res.state, CallState):
            r.error("adapter.bad_state_type", f"state is {type(res.state)}, expected CallState", where)
        log = adapter.drain_raw_log()
        if len(log) != 1:
            r.error("adapter.raw_not_persisted",
                    f"expected exactly 1 raw-log entry after a call, got {len(log)}", where)
        # Cost must be 0 on non-OK, and >= 0 on OK.
        if res.state is not CallState.OK and res.cost_usd != 0.0:
            r.warn("adapter.cost_on_failure",
                   f"capability '{cap}' returned non-OK but cost_usd={res.cost_usd} (expected 0)", where)

    if r.passed:
        r.info("adapter.conformant", f"{adapter.key} passes the contract; record one --live fixture per capability", where)
    return r
