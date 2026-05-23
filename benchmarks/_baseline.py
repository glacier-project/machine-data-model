"""Load, save, and compare baseline.json files."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from benchmarks._harness import ScenarioResult


@dataclass(frozen=True)
class BaselineEntry:
    """One scenario's reference numbers."""

    ops_per_sec: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    samples: int


@dataclass
class Baseline:
    """Top-level baseline.json structure."""

    version: str
    captured_at: str
    machine: dict[str, str]
    scenarios: dict[str, BaselineEntry] = field(default_factory=dict)


def load(path: Path) -> Baseline:
    """Read a baseline.json file."""
    raw = json.loads(path.read_text())
    return Baseline(
        version=raw["version"],
        captured_at=raw["captured_at"],
        machine=dict(raw["machine"]),
        scenarios={
            k: BaselineEntry(**v) for k, v in raw["scenarios"].items()
        },
    )


def save(path: Path, baseline: Baseline) -> None:
    """Write a baseline.json file with stable key ordering."""
    payload: dict[str, Any] = {
        "version": baseline.version,
        "captured_at": baseline.captured_at,
        "machine": baseline.machine,
        "scenarios": {
            k: {
                "ops_per_sec": v.ops_per_sec,
                "p50_ms": v.p50_ms,
                "p95_ms": v.p95_ms,
                "p99_ms": v.p99_ms,
                "samples": v.samples,
            }
            for k, v in sorted(baseline.scenarios.items())
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


THRESHOLD = 0.10  # 10% regression tolerance


@dataclass
class CompareReport:
    """Result of comparing a current run against a baseline."""

    regressions: list[str] = field(default_factory=list)
    missing_in_current: list[str] = field(default_factory=list)
    missing_in_baseline: list[str] = field(default_factory=list)
    # per-scenario relative deltas (positive ops_per_sec == faster;
    # positive p95_ms / p99_ms == slower)
    deltas: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        """True if anything regressed or a baselined scenario went missing."""
        return bool(self.regressions) or bool(self.missing_in_current)


def compare(
    baseline: Baseline,
    current: dict[str, ScenarioResult],
    threshold: float = THRESHOLD,
) -> CompareReport:
    """Compare a fresh run against ``baseline``.

    Rules:
      - ``ops_per_sec`` regresses if ``current < (1 - threshold) * baseline``.
      - ``p95_ms`` / ``p99_ms`` regress if
        ``current > (1 + threshold) * baseline``.
      - In baseline + missing in current -> ERROR (counted as failure).
      - In current + missing in baseline -> WARNING (not a failure).
    """
    report = CompareReport()
    for key, entry in baseline.scenarios.items():
        if key not in current:
            report.missing_in_current.append(key)
            continue
        c = current[key]
        ops_delta = (
            (c.ops_per_sec - entry.ops_per_sec) / entry.ops_per_sec
            if entry.ops_per_sec
            else 0.0
        )
        p95_delta = (
            (c.p95_ms - entry.p95_ms) / entry.p95_ms if entry.p95_ms else 0.0
        )
        p99_delta = (
            (c.p99_ms - entry.p99_ms) / entry.p99_ms if entry.p99_ms else 0.0
        )
        report.deltas[key] = {
            "ops_per_sec": ops_delta,
            "p95_ms": p95_delta,
            "p99_ms": p99_delta,
        }
        if (
            ops_delta < -threshold
            or p95_delta > threshold
            or p99_delta > threshold
        ):
            report.regressions.append(key)

    for key in current:
        if key not in baseline.scenarios:
            report.missing_in_baseline.append(key)
    return report
