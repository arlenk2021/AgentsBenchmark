"""Mock adapters for the Stage-3 dry run and the test suite.

`PerfectMockAdapter` is the "mocked perfect vendor" the playbook's Stage-3 exit
criterion requires: running the scorer against it on a handful of rows must return
fidelity 1.0, which catches schema/scorer mismatches before any real API spend.
`FaultyMockAdapter` exercises the error-mapping and no-coverage paths.
"""
from __future__ import annotations

from typing import Any

from .base import VendorAdapter, VendorHTTPError, VendorTimeout


class PerfectMockAdapter(VendorAdapter):
    """Returns the exact golden truth for every row it is asked about.

    Constructed with a {row_id: golden_dict} map — only legitimate in a dry run,
    where the point is to validate the harness, not the vendor.
    """
    key = "mock_perfect"

    def __init__(self, truth: dict[str, dict], **kw):
        super().__init__(cost_table=kw.pop("cost_table", {"extract": 0.001}), **kw)
        self._truth = truth

    def capabilities(self) -> list[str]:
        return ["extract"]

    def _invoke(self, capability: str, *, row_id: str = "", **kwargs) -> tuple[Any, Any]:
        golden = self._truth.get(row_id, {})
        return dict(golden), {"row_id": row_id, "echo_golden": golden}


class FaultyMockAdapter(VendorAdapter):
    """Deterministically injects each failure mode by row index, so tests and the
    dry run see every CallState and the no-coverage path."""
    key = "mock_faulty"

    def __init__(self, truth: dict[str, dict], order: list[str] | None = None, **kw):
        super().__init__(cost_table=kw.pop("cost_table", {"extract": 0.001}), **kw)
        self._truth = truth
        self._order = order or list(truth.keys())

    def capabilities(self) -> list[str]:
        return ["extract"]

    def _invoke(self, capability: str, *, row_id: str = "", **kwargs) -> tuple[Any, Any]:
        idx = self._order.index(row_id) if row_id in self._order else 0
        mode = idx % 5
        if mode == 1:
            raise VendorHTTPError(403, "forbidden")        # -> blocked
        if mode == 2:
            raise VendorTimeout("deadline exceeded")        # -> timeout
        if mode == 3:
            raise VendorHTTPError(500, "server error")      # -> fetch_failed
        if mode == 4:
            return {}, {"row_id": row_id}                   # empty -> no_coverage
        return dict(self._truth.get(row_id, {})), {"row_id": row_id}  # correct
