"""Smoke tests that exercise the runner CLI as a subprocess."""

import json
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


def test_runner_unknown_scenario_exits_nonzero() -> None:
    repo = Path(__file__).resolve().parents[2]
    proc = _run("--scenario", "no.such.scenario", cwd=repo)
    assert proc.returncode != 0
    assert "no.such.scenario" in (proc.stdout + proc.stderr)


def test_runner_no_args_exits_zero_and_produces_output() -> None:
    # Running with no --scenario filter runs all registered scenarios
    # and exits 0.  When at least one scenario is registered the output
    # must contain the ops/s header; when the registry is empty the
    # runner prints "no scenarios run." — either way exit code is 0.
    repo = Path(__file__).resolve().parents[2]
    proc = _run(cwd=repo)
    assert proc.returncode == 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "no scenarios" in combined or "ops/s" in combined


def test_runner_runs_coalescer_notify_tiny_duration(tmp_path: Path) -> None:
    """The simplest real scenario must produce >0 ops/s in ~0.3s."""
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "coalescer.notify",
        "--duration",
        "0.2",
        "--warmup",
        "0.1",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    payload = json.loads(out.read_text())
    assert "coalescer.notify" in payload["scenarios"]
    assert payload["scenarios"]["coalescer.notify"]["ops_per_sec"] > 0
