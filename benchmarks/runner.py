"""CLI entry point for the exposer benchmark harness.

Usage:
    python -m benchmarks.runner [--scenario ID] [--duration S]
                                [--warmup S] [--json PATH]
                                [--save-baseline] [--compare]
                                [--sweep]
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

from benchmarks._harness import (
    run_scenario,
    scenario_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from benchmarks._harness import Scenario, ScenarioResult

DEFAULT_DURATION_S = 5.0
DEFAULT_WARMUP_S = 1.0

# Each bench_* module appends its scenarios here via register_scenarios().
# Modules are imported in this list (statically); adding a new benchmark
# means adding one line below.
_BENCH_MODULES: list[str] = []


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


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run selected scenarios, and print results."""
    from pathlib import Path as _Path

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
        type=_Path,
        help="Write machine-readable JSON results to this path.",
    )
    args = parser.parse_args(argv)

    scenarios = _discover_scenarios()
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
