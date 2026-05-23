"""Load, save, and compare baseline.json files."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


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
