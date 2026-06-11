"""The vendor-adapter contract (Stage 4).

`adapters/base.py` is named in the playbook as *the contract*. The cardinal rule:
**adapters transport, they never normalize meaning.** If you are tempted to "fix" a
vendor's weird output here, that is a scoring rule — it belongs in `scoring/`, where
it is public and applied uniformly to every vendor.

Every adapter therefore does only four things:
  1. declares its capabilities (calling an undeclared one raises),
  2. issues the call and persists the raw response (audit trail),
  3. maps transport/auth errors to a terminal `CallState`,
  4. reports billed cost from the Stage-1 cost table.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CallState(str, Enum):
    OK = "ok"
    BLOCKED = "blocked"          # 401/402/403 — auth, payment, forbidden
    TIMEOUT = "timeout"
    FETCH_FAILED = "fetch_failed"  # everything else (5xx, parse, network)


class AdapterError(Exception):
    """Raised for contract violations (e.g. calling an undeclared capability)."""


class VendorTimeout(Exception):
    pass


class VendorHTTPError(Exception):
    def __init__(self, status: int, message: str = ""):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


@dataclass
class CallResult:
    state: CallState
    value: Any = None                  # parsed-but-not-normalized payload the scorer reads
    raw: Any = None                    # full vendor response, persisted on every call
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    capability: str = ""
    vendor: str = ""
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.state is CallState.OK


def map_error(exc: Exception) -> CallState:
    """Uniform error mapping (Stage 4 checklist): 401/402/403 -> blocked;
    timeouts -> timeout; everything else -> fetch_failed."""
    if isinstance(exc, VendorTimeout):
        return CallState.TIMEOUT
    if isinstance(exc, VendorHTTPError) and exc.status in (401, 402, 403):
        return CallState.BLOCKED
    return CallState.FETCH_FAILED


class VendorAdapter(abc.ABC):
    """Base class for every vendor adapter.

    Subclasses implement `capabilities()` and `_invoke()`. They MUST NOT override
    `call()` — it owns timing, raw persistence, error mapping, and the
    undeclared-capability guard, so that behaviour is uniform across vendors.
    """

    key: str = "unset"

    def __init__(self, cost_table: dict[str, float] | None = None, plan: str | None = None):
        # cost_table comes from the primitive YAML (sourced from the Stage-1 pricing PDF).
        self.cost_table = cost_table or {}
        self.plan = plan
        self._raw_log: list[dict] = []   # audit trail; flushed to the snapshot artifact

    @abc.abstractmethod
    def capabilities(self) -> list[str]:
        """Declared capabilities, e.g. ['extract', 'crawl']. Undeclared => raises."""

    @abc.abstractmethod
    def _invoke(self, capability: str, **kwargs) -> tuple[Any, Any]:
        """Do the real call. Return (value, raw). May raise VendorTimeout /
        VendorHTTPError / any Exception — `call()` maps it to a CallState."""

    def cost_for(self, capability: str, units: float = 1.0) -> float:
        """Billed cost from the pinned plan's cost table. Never guessed."""
        return float(self.cost_table.get(capability, 0.0)) * units

    def call(self, capability: str, *, units: float = 1.0, **kwargs) -> CallResult:
        if capability not in self.capabilities():
            raise AdapterError(
                f"{self.key}: capability '{capability}' is not declared — "
                "undeclared capabilities must raise, never silently no-op"
            )
        t0 = time.perf_counter()
        try:
            value, raw = self._invoke(capability, **kwargs)
            state = CallState.OK
            error = None
        except Exception as exc:  # noqa: BLE001 — uniform mapping is the point
            value, raw, error = None, getattr(exc, "raw", None), str(exc)
            state = map_error(exc)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        result = CallResult(
            state=state, value=value, raw=raw,
            cost_usd=self.cost_for(capability, units) if state is CallState.OK else 0.0,
            latency_ms=latency_ms, capability=capability, vendor=self.key, error=error,
        )
        # Raw persisted on EVERY call (success or failure) — audit trail.
        self._raw_log.append({
            "vendor": self.key, "capability": capability, "state": state.value,
            "kwargs": kwargs, "raw": raw, "cost_usd": result.cost_usd,
            "latency_ms": latency_ms, "error": error,
        })
        return result

    def drain_raw_log(self) -> list[dict]:
        log, self._raw_log = self._raw_log, []
        return log
