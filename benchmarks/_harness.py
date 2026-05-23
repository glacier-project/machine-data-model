"""Shared timer + aggregation primitives for exposer benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
import time
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


def aggregate(
    name: str,
    params: dict[str, Any],
    samples: list[Sample],
    window_s: float,
) -> ScenarioResult:
    """Compute ops/sec and latency percentiles from raw samples."""
    latencies_ns = [s.latency_ns for s in samples]
    n = len(samples)
    ops_per_sec = n / window_s if window_s > 0 else 0.0
    return ScenarioResult(
        scenario_key=scenario_key(name, params),
        name=name,
        params=params,
        ops_per_sec=ops_per_sec,
        p50_ms=_percentile(latencies_ns, 50.0) / 1e6,
        p95_ms=_percentile(latencies_ns, 95.0) / 1e6,
        p99_ms=_percentile(latencies_ns, 99.0) / 1e6,
        samples=n,
        window_s=window_s,
    )


def run_scenario(
    scenario: Scenario,
    duration_s: float,
    warmup_s: float,
) -> ScenarioResult:
    """Drive a scenario: setup -> warmup -> measure -> teardown."""
    scenario.setup()
    try:
        if warmup_s > 0:
            scenario.run(warmup_s)
        t0 = time.monotonic()
        samples = scenario.run(duration_s)
        window_s = time.monotonic() - t0
    finally:
        scenario.teardown()
    return aggregate(scenario.name, scenario.params, samples, window_s)
