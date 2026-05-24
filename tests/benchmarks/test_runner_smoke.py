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


def test_runner_runs_coalescer_drain_tiny_duration(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "coalescer.drain",
        "--duration",
        "0.3",
        "--warmup",
        "0.1",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert "coalescer.drain" in payload["scenarios"]
    assert payload["scenarios"]["coalescer.drain"]["ops_per_sec"] > 0


def test_runner_runs_http_read_tiny_duration(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "http.read",
        "--duration",
        "0.5",
        "--warmup",
        "0.2",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    # Default params: concurrency=32
    assert "http.read[concurrency=32]" in payload["scenarios"]
    assert payload["scenarios"]["http.read[concurrency=32]"]["ops_per_sec"] > 0


def test_runner_runs_http_write_tiny_duration(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "http.write",
        "--duration",
        "0.5",
        "--warmup",
        "0.2",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert "http.write[concurrency=32]" in payload["scenarios"]
    assert payload["scenarios"]["http.write[concurrency=32]"]["ops_per_sec"] > 0


def test_runner_runs_http_method_tiny_duration(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "http.method",
        "--duration",
        "0.5",
        "--warmup",
        "0.2",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert "http.method[concurrency=32]" in payload["scenarios"]
    assert (
        payload["scenarios"]["http.method[concurrency=32]"]["ops_per_sec"] > 0
    )


def test_runner_runs_ws_fanout_tiny_duration(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "out.json"
    proc = _run(
        "--scenario",
        "ws.fanout",
        "--duration",
        "0.5",
        "--warmup",
        "0.2",
        "--json",
        str(out),
        cwd=repo,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text())
    assert "ws.fanout[subscribers=100]" in payload["scenarios"]
    assert payload["scenarios"]["ws.fanout[subscribers=100]"]["ops_per_sec"] > 0
