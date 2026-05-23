"""Unit tests for the baseline JSON load/save/compare module."""

from pathlib import Path

from benchmarks._baseline import (
    Baseline,
    BaselineEntry,
    compare,
    load,
    save,
)
from benchmarks._harness import ScenarioResult


def _example_baseline() -> Baseline:
    return Baseline(
        version="1.0.0",
        captured_at="2026-05-23T12:00:00Z",
        machine={"cpu": "fake-cpu", "python": "3.11.0", "os": "linux-x86_64"},
        scenarios={
            "http.read[concurrency=32]": BaselineEntry(
                ops_per_sec=4521.3,
                p50_ms=6.8,
                p95_ms=12.4,
                p99_ms=18.0,
                samples=22606,
            ),
        },
    )


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    original = _example_baseline()
    save(path, original)
    loaded = load(path)
    assert loaded == original


def test_save_writes_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    save(path, _example_baseline())
    assert path.read_text().endswith("\n")


def _result(
    key: str,
    name: str,
    ops: float,
    p50: float = 1.0,
    p95: float = 1.0,
    p99: float = 1.0,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_key=key,
        name=name,
        params={},
        ops_per_sec=ops,
        p50_ms=p50,
        p95_ms=p95,
        p99_ms=p99,
        samples=int(ops),
        window_s=1.0,
    )


def test_compare_no_change_no_regression() -> None:
    base = _example_baseline()
    current = {
        "http.read[concurrency=32]": _result(
            "http.read[concurrency=32]",
            "http.read",
            ops=4521.3,
            p50=6.8,
            p95=12.4,
            p99=18.0,
        )
    }
    report = compare(base, current)
    assert report.regressions == []
    assert report.missing_in_current == []
    assert report.missing_in_baseline == []
    assert not report.failed


def test_compare_ops_drop_15pct_is_regression() -> None:
    base = _example_baseline()
    # 15% slower than 4521.3 -> 3843.1
    current = {
        "http.read[concurrency=32]": _result(
            "http.read[concurrency=32]",
            "http.read",
            ops=3843.1,
            p50=6.8,
            p95=12.4,
            p99=18.0,
        )
    }
    report = compare(base, current)
    assert report.regressions == ["http.read[concurrency=32]"]
    assert report.failed


def test_compare_ops_drop_5pct_is_not_regression() -> None:
    base = _example_baseline()
    # 5% slower (within threshold) -> 4295.2
    current = {
        "http.read[concurrency=32]": _result(
            "http.read[concurrency=32]",
            "http.read",
            ops=4295.2,
            p50=6.8,
            p95=12.4,
            p99=18.0,
        )
    }
    report = compare(base, current)
    assert report.regressions == []
    assert not report.failed


def test_compare_p95_increase_15pct_is_regression() -> None:
    base = _example_baseline()
    # ops same, p95 15% higher: 12.4 -> 14.26
    current = {
        "http.read[concurrency=32]": _result(
            "http.read[concurrency=32]",
            "http.read",
            ops=4521.3,
            p50=6.8,
            p95=14.26,
            p99=18.0,
        )
    }
    report = compare(base, current)
    assert report.regressions == ["http.read[concurrency=32]"]


def test_compare_missing_in_current_is_failure() -> None:
    base = _example_baseline()
    report = compare(base, {})  # no current results
    assert report.missing_in_current == ["http.read[concurrency=32]"]
    assert report.failed


def test_compare_missing_in_baseline_is_warning_not_failure() -> None:
    base = Baseline(
        version="1.0.0",
        captured_at="2026-05-23T12:00:00Z",
        machine={"cpu": "x", "python": "y", "os": "z"},
        scenarios={},
    )
    current = {
        "new.scenario": _result("new.scenario", "new.scenario", ops=100.0)
    }
    report = compare(base, current)
    assert report.missing_in_baseline == ["new.scenario"]
    assert report.regressions == []
    assert not report.failed
