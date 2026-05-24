"""CLI entry point for the exposer benchmark harness.

Usage:
    python -m benchmarks.runner [--scenario ID] [--duration S]
                                [--warmup S] [--json PATH]
                                [--save-baseline] [--compare]
                                [--sweep]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import platform
import sys
from typing import TYPE_CHECKING

from benchmarks._baseline import (
    Baseline,
    BaselineEntry,
    compare,
    load,
    save,
)
from benchmarks._harness import (
    run_scenario,
    scenario_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from benchmarks._baseline import CompareReport
    from benchmarks._harness import Scenario, ScenarioResult

DEFAULT_DURATION_S = 5.0
DEFAULT_WARMUP_S = 1.0
DEFAULT_BASELINE_PATH = Path("benchmarks/baseline.json")

# Each bench_* module appends its scenarios here via register_scenarios().
# Modules are imported in this list (statically); adding a new benchmark
# means adding one line below.
_BENCH_MODULES: list[str] = [
    "benchmarks.bench_coalescer",
    "benchmarks.bench_http",
    "benchmarks.bench_ws",
]


def _expand_sweep(scenarios: list[Scenario]) -> list[Scenario]:
    """Expand each scenario by its SWEEP_PARAMS (cartesian product)."""
    import copy
    import itertools

    expanded: list[Scenario] = []
    for s in scenarios:
        sweep = getattr(s, "SWEEP_PARAMS", None)
        if not sweep:
            expanded.append(s)
            continue
        keys = list(sweep.keys())
        values_lists = [sweep[k] for k in keys]
        for combo in itertools.product(*values_lists):
            clone = copy.copy(s)
            clone.params = dict(zip(keys, combo, strict=True))
            expanded.append(clone)
    return expanded


def _discover_scenarios() -> list[Scenario]:
    """Import each bench_* module and collect its scenarios."""
    import importlib

    scenarios: list[Scenario] = []
    for mod_name in _BENCH_MODULES:
        mod = importlib.import_module(mod_name)
        scenarios.extend(mod.register_scenarios())
    return scenarios


def _filter_scenarios(
    scenarios: Iterable[Scenario], wanted: str | None
) -> list[Scenario]:
    """Return scenarios whose ``name`` or full key matches ``wanted``.

    ``wanted=None`` -> return all. ``wanted="http.read"`` matches every
    parameterized variant. ``wanted="http.read[concurrency=32]"`` matches
    that exact variant only.
    """
    if wanted is None:
        return list(scenarios)
    result: list[Scenario] = []
    for s in scenarios:
        if s.name == wanted or scenario_key(s.name, s.params) == wanted:
            result.append(s)
    return result


def _print_summary(results: list[ScenarioResult]) -> None:
    """Print a simple text table to stdout."""
    if not results:
        print("no scenarios run.")
        return
    header = (
        f"{'scenario':<40} {'ops/s':>12} {'p50ms':>8}"
        f" {'p95ms':>8} {'p99ms':>8} {'n':>8}"
    )
    print(header)
    print("-" * len(header))
    for r in sorted(results, key=lambda x: x.scenario_key):
        print(
            f"{r.scenario_key:<40} "
            f"{r.ops_per_sec:>12.1f} "
            f"{r.p50_ms:>8.3f} "
            f"{r.p95_ms:>8.3f} "
            f"{r.p99_ms:>8.3f} "
            f"{r.samples:>8d}"
        )


def _write_json(path: Path, results: list[ScenarioResult]) -> None:
    payload = {
        "scenarios": {
            r.scenario_key: {
                "ops_per_sec": r.ops_per_sec,
                "p50_ms": r.p50_ms,
                "p95_ms": r.p95_ms,
                "p99_ms": r.p99_ms,
                "samples": r.samples,
                "window_s": r.window_s,
                "params": r.params,
            }
            for r in results
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _project_version() -> str:
    """Return the project version from pyproject.toml ([project] version)."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    for raw_line in pyproject.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("version") and "=" in line:
            # e.g. version = "1.0.0"
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return "unknown"


def _capture_machine_info() -> dict[str, str]:
    """Capture CPU / Python / OS strings used to tag a baseline file."""
    return {
        "cpu": platform.processor() or platform.machine() or "unknown",
        "python": platform.python_version(),
        "os": f"{platform.system().lower()}-{platform.machine()}",
    }


def _results_to_baseline(results: list[ScenarioResult]) -> Baseline:
    """Wrap fresh scenario results into a Baseline payload for save()."""
    return Baseline(
        version=_project_version(),
        captured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        machine=_capture_machine_info(),
        scenarios={
            r.scenario_key: BaselineEntry(
                ops_per_sec=r.ops_per_sec,
                p50_ms=r.p50_ms,
                p95_ms=r.p95_ms,
                p99_ms=r.p99_ms,
                samples=r.samples,
            )
            for r in results
        },
    )


def _print_compare(report: CompareReport) -> None:
    """Print a per-scenario delta table and any warning/error messages."""
    if report.deltas:
        header = (
            f"{'scenario':<40} {'ops_delta':>10}"
            f" {'p95_delta':>10} {'p99_delta':>10}"
        )
        print(header)
        print("-" * len(header))
        for key in sorted(report.deltas):
            d = report.deltas[key]
            print(
                f"{key:<40} "
                f"{d['ops_per_sec'] * 100:>+9.2f}% "
                f"{d['p95_ms'] * 100:>+9.2f}% "
                f"{d['p99_ms'] * 100:>+9.2f}%"
            )
    if report.missing_in_baseline:
        print()
        print(
            "WARNING: scenarios not in baseline (re-save before release):"
        )
        for k in report.missing_in_baseline:
            print(f"  - {k}")
    if report.missing_in_current:
        print()
        print("ERROR: scenarios in baseline but missing in this run:")
        for k in report.missing_in_current:
            print(f"  - {k}")
    if report.regressions:
        print()
        print("ERROR: regressions exceeding threshold:")
        for k in report.regressions:
            print(f"  - {k}")


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run selected scenarios, and print results."""
    parser = argparse.ArgumentParser(prog="benchmarks.runner")
    parser.add_argument(
        "--scenario",
        help="Run only this scenario (bare name or full key).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help=f"Measurement window seconds (default: {DEFAULT_DURATION_S}).",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=DEFAULT_WARMUP_S,
        help=f"Warmup seconds, discarded (default: {DEFAULT_WARMUP_S}).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Write machine-readable JSON results to this path.",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save the current run's results as the new baseline.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help=(
            "Compare results against the baseline and exit nonzero on "
            "regression."
        ),
    )
    parser.add_argument(
        "--baseline-path",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help=f"Baseline file path (default: {DEFAULT_BASELINE_PATH}).",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Expand each scenario across its SWEEP_PARAMS.",
    )
    args = parser.parse_args(argv)

    scenarios = _discover_scenarios()
    if args.sweep:
        scenarios = _expand_sweep(scenarios)
    selected = _filter_scenarios(scenarios, args.scenario)

    if args.scenario and not selected:
        print(
            f"error: scenario {args.scenario!r} not found.",
            file=sys.stderr,
        )
        return 2

    results: list[ScenarioResult] = []
    for s in selected:
        print(f"running {scenario_key(s.name, s.params)} ...", flush=True)
        result = run_scenario(s, args.duration, args.warmup)
        results.append(result)

    _print_summary(results)
    if args.json is not None:
        _write_json(args.json, results)

    if args.save_baseline:
        baseline = _results_to_baseline(results)
        save(args.baseline_path, baseline)
        print(f"baseline saved to {args.baseline_path}")

    if args.compare:
        if not args.baseline_path.exists():
            print(
                f"error: baseline file not found: {args.baseline_path}",
                file=sys.stderr,
            )
            return 2
        baseline = load(args.baseline_path)
        current = {r.scenario_key: r for r in results}
        report = compare(baseline, current)
        _print_compare(report)
        if report.failed:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
