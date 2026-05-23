"""Unit tests for the benchmark harness primitives."""

from benchmarks._harness import _percentile


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
