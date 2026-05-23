"""Unit tests for the baseline JSON load/save/compare module."""

from pathlib import Path

from benchmarks._baseline import (
    Baseline,
    BaselineEntry,
    load,
    save,
)


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
