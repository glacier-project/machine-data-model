# Exposer Benchmarks

Manual benchmark harness for the `machine_data_model.exposers` subsystem.

## Run all scenarios

```bash
uv run python -m benchmarks.runner
```

Default per-scenario settings: 1.0s warmup + 5.0s measurement. Total wall-time at defaults is roughly 30-45 seconds.

## Run a single scenario

```bash
uv run python -m benchmarks.runner --scenario http.read
uv run python -m benchmarks.runner --scenario "http.read[concurrency=32]"
```

The bare name matches every parameterized variant; the full key matches one.

## Override durations

```bash
uv run python -m benchmarks.runner --duration 10 --warmup 2
```

## Parameter sweeps

```bash
uv run python -m benchmarks.runner --sweep
```

Expands HTTP scenarios across `concurrency in {1, 8, 32, 128}` and `ws.fanout` across `subscribers in {1, 10, 100, 1000}`. Multiplies wall-time accordingly.

## Refresh the baseline before a release

```bash
uv run python -m benchmarks.runner --save-baseline
```

This overwrites `benchmarks/baseline.json` with the results of the current run, tagged with the current `pyproject.toml` version, ISO-8601 capture time, and machine info (CPU, Python, OS). The maintainer runs this **once per release**, on the **same reference machine** every time.

## Regression check

```bash
uv run python -m benchmarks.runner --compare
```

Exits `1` if any scenario regresses by more than **10%** relative to `baseline.json` -- `ops_per_sec` below `0.9x` baseline, or `p95_ms` / `p99_ms` above `1.1x` baseline. Prints a per-scenario delta table regardless.

If a scenario in the baseline is missing from the current run, that is treated as an **error** (exit 1). If a scenario in the current run is missing from the baseline, that is treated as a **warning** (exit 0); refresh the baseline at the next release.

## Machine sensitivity

**`baseline.json` is machine-specific.** It is captured on the maintainer's release box; absolute numbers on your laptop will differ. The intended developer workflow for a refactor is:

1. On `main` (or pre-change): `python -m benchmarks.runner --save-baseline --baseline-path /tmp/before.json`
2. Make your change.
3. `python -m benchmarks.runner --compare --baseline-path /tmp/before.json`

This compares the **same machine** before and after the change, which cancels hardware noise. Use the repo-tracked `benchmarks/baseline.json` only for absolute reference numbers, not as a pass/fail gate on arbitrary machines.

## Noise reduction

- Close other applications and browser tabs.
- If on a laptop, plug it in (CPU governor matters).
- Run the same scenario twice and discard the first result.
- If a scenario's number is fluttering by +/-20%, increase `--duration` to 20s.

## Architecture

- `_harness.py` -- `Sample`, `ScenarioResult`, percentile calc, `run_scenario()` (warmup pass + measurement pass)
- `_baseline.py` -- `Baseline` dataclass, `load`/`save`/`compare`
- `runner.py` -- argparse CLI, scenario discovery, sweep expansion, output
- `bench_coalescer.py` -- `coalescer.notify`, `coalescer.drain`
- `bench_http.py` -- `http.read`, `http.write`, `http.method` (shares `_HttpFixture`)
- `bench_ws.py` -- `ws.fanout`, `ws.e2e_latency` (shares `_WsFixture`)

Adding a new benchmark: write a `Scenario`-protocol class in a new `bench_<topic>.py`, expose `register_scenarios()`, and append the module name to `_BENCH_MODULES` in `runner.py`.
