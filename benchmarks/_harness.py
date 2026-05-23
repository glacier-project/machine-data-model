"""Shared timer + aggregation primitives for exposer benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Sample:
    """One measured operation.

    ``latency_ns`` may be 0 for scenarios where per-op timing would
    dominate the cost being measured (e.g. coalescer microbench). The
    aggregator still computes throughput correctly in that case because
    it counts samples regardless of their latency value.
    """

    latency_ns: int


@dataclass
class ScenarioResult:
    """Aggregated output of one scenario run.

    Latencies are reported in **milliseconds** (``p50_ms``, ``p95_ms``,
    ``p99_ms``) for human readability. Raw samples store latency in
    **nanoseconds** (``Sample.latency_ns``); the aggregator divides by
    1e6 when populating the percentile fields.
    """

    scenario_key: str
    name: str
    params: dict[str, Any]
    ops_per_sec: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    samples: int
    window_s: float


class Scenario(Protocol):
    """Protocol every benchmark scenario implements."""

    name: str
    params: dict[str, Any]

    def setup(self) -> None: ...
    def run(self, duration_s: float) -> list[Sample]: ...
    def teardown(self) -> None: ...


def scenario_key(name: str, params: dict[str, Any]) -> str:
    """Render ``name[k=v,...]`` (alphabetical) for a scenario instance."""
    if not params:
        return name
    inner = ",".join(f"{k}={params[k]}" for k in sorted(params))
    return f"{name}[{inner}]"


def _percentile(values: list[int], pct: float) -> float:
    """Linear-interpolation percentile. Returns 0.0 on empty input."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac
