"""Unit tests for the benchmark harness primitives."""

from __future__ import annotations

import pytest

from benchmarks._harness import (
    Sample,
    _percentile,
    aggregate,
    run_scenario,
    scenario_key,
)


def test_percentile_empty_returns_zero() -> None:
    assert _percentile([], 50.0) == 0.0


def test_percentile_single_value() -> None:
    assert _percentile([100], 50.0) == 100.0
    assert _percentile([100], 99.0) == 100.0


def test_percentile_sorted_input_p50() -> None:
    # 0..100 inclusive, 101 values; p50 == 50
    values = list(range(0, 101))
    assert _percentile(values, 50.0) == 50.0


def test_percentile_unsorted_input_p95() -> None:
    # Same values shuffled; result identical because we sort internally.
    values = list(range(100, -1, -1))
    assert _percentile(values, 95.0) == 95.0


def test_percentile_interpolates_between_samples() -> None:
    # Two values: linear interpolation between them at p50 -> midpoint.
    assert _percentile([10, 20], 50.0) == 15.0


def test_scenario_key_no_params() -> None:
    assert scenario_key("http.read", {}) == "http.read"


def test_scenario_key_sorted_params() -> None:
    # Keys are sorted alphabetically regardless of insertion order.
    assert (
        scenario_key("ws.fanout", {"subscribers": 100, "duration": 5})
        == "ws.fanout[duration=5,subscribers=100]"
    )


def test_aggregate_ops_per_sec() -> None:
    samples = [Sample(latency_ns=1_000_000) for _ in range(100)]
    result = aggregate("x", {}, samples, window_s=2.0)
    assert result.ops_per_sec == 50.0
    assert result.samples == 100
    assert result.window_s == 2.0


def test_aggregate_percentiles_in_ms() -> None:
    # 100 samples with latency = i microseconds -> i * 1000 ns
    samples = [Sample(latency_ns=i * 1_000) for i in range(1, 101)]
    result = aggregate("x", {}, samples, window_s=1.0)
    # p50 of 1..100 us = 50.5 us = 0.0505 ms
    assert abs(result.p50_ms - 0.0505) < 1e-6
    # p95 = 95.05 us = 0.09505 ms
    assert abs(result.p95_ms - 0.09505) < 1e-6


def test_aggregate_zero_window_returns_zero_ops() -> None:
    result = aggregate("x", {}, [Sample(latency_ns=1)], window_s=0.0)
    assert result.ops_per_sec == 0.0


class _FakeScenario:
    """Records how many times run() was called and with what duration."""

    name = "fake"

    def __init__(self) -> None:
        self.params: dict[str, object] = {}
        self.run_calls: list[float] = []
        self.setup_called = False
        self.teardown_called = False

    def setup(self) -> None:
        self.setup_called = True

    def run(self, duration_s: float) -> list[Sample]:
        self.run_calls.append(duration_s)
        # Pretend the scenario produced 10 samples per run() call.
        return [Sample(latency_ns=1) for _ in range(10)]

    def teardown(self) -> None:
        self.teardown_called = True


def test_run_scenario_calls_setup_warmup_run_teardown() -> None:
    fake = _FakeScenario()
    result = run_scenario(fake, duration_s=0.01, warmup_s=0.005)
    assert fake.setup_called
    assert fake.teardown_called
    # Two run() calls: warmup, then measurement
    assert len(fake.run_calls) == 2
    assert fake.run_calls[0] == 0.005
    assert fake.run_calls[1] == 0.01
    # Only the measurement samples (10) are aggregated
    assert result.samples == 10


def test_run_scenario_skips_warmup_when_zero() -> None:
    fake = _FakeScenario()
    run_scenario(fake, duration_s=0.01, warmup_s=0.0)
    assert len(fake.run_calls) == 1
    assert fake.run_calls[0] == 0.01


def test_run_scenario_calls_teardown_on_run_exception() -> None:
    class _Boom:
        name = "boom"

        def __init__(self) -> None:
            self.params: dict[str, object] = {}
            self.teardown_called = False

        def setup(self) -> None:
            pass

        def run(self, duration_s: float) -> list[Sample]:
            raise RuntimeError("boom")

        def teardown(self) -> None:
            self.teardown_called = True

    b = _Boom()
    with pytest.raises(RuntimeError, match="boom"):
        run_scenario(b, duration_s=0.01, warmup_s=0.0)
    assert b.teardown_called
