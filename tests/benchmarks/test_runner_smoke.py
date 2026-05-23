"""Smoke tests that exercise the runner CLI as a subprocess."""

import json  # noqa: F401  # used by later tasks
from pathlib import Path
import subprocess
import sys


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "benchmarks.runner", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_runner_unknown_scenario_exits_nonzero(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    proc = _run("--scenario", "no.such.scenario", cwd=repo)
    assert proc.returncode != 0
    assert "no.such.scenario" in (proc.stdout + proc.stderr)


def test_runner_no_scenarios_registered_prints_message(tmp_path: Path) -> None:
    # With the empty registry, running with no filter is a no-op:
    # we expect a friendly "no scenarios registered" line, exit 0.
    repo = Path(__file__).resolve().parents[2]
    proc = _run(cwd=repo)
    assert proc.returncode == 0
    assert "no scenarios" in (proc.stdout + proc.stderr).lower()
