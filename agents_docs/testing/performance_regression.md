# Performance Regression Protocol

## Purpose

`tools.performance` supplies a dependency-free benchmark harness for phase-by-phase refactoring. It measures production-like operations independently from unit-test duration and stores the raw samples needed to audit every gate decision.

## Public interface

Create a `BenchmarkScenario` with a descriptive name, an explicit `cold` or `warm` cache label, and a zero-argument operation. The runner enforces three warmups and ten measured runs by default. Approved long-running calibration, detection, triangulation, and export scenarios may set `approved_long_workflow=True` and `measured_runs=5`; five runs are rejected without that explicit marker.

```python
from tools.performance import BenchmarkRunner, BenchmarkScenario

scenario = BenchmarkScenario(
    name="detections-session-summary",
    cache_state="warm",
    operation=load_detection_summary,
    before_each=restore_controlled_fixture,
    maximum_p95_ms=500.0,
)
result = BenchmarkRunner().run(scenario)
```

The operation may return `BenchmarkObservation(work_units, unit_name)` to report aggregate throughput. If any successful run supplies an observation, all successful runs must use the same unit. The comparison gate requires identical per-run work and units, then rejects throughput more than 3% below baseline. Failures are retained in the result instead of terminating the remaining measurements.

Use `write_report(path, results, metadata)` and `read_report(path)` for the versioned JSON format. The report includes raw samples, configured run counts, p50/median, nearest-rank p95, minimum, maximum, measured and warmup failures, and throughput when supplied. `compare_report_files(baseline_path, candidate_path)` is the phase gate because it verifies controlled-environment metadata as well as measurements. `compare_reports(...)` is available for unit-level comparisons where the caller separately controls the environment.

`tools/performance/run_http_benchmarks.py` is the SDK-style executable for read-only HTTP scenarios. Set its constants, `BENCHMARK_METADATA`, and `HTTP_SCENARIOS` at the top of the file; it deliberately has no command-line parser. Run it from the repository root with `python -m tools.performance.run_http_benchmarks`. Service-specific suites may import the public API directly instead of changing that shared runner.

The production browser runner is dependency-free and uses Node's built-in
WebSocket plus Chrome DevTools Protocol:

```powershell
node --test tools/performance/browser/tests/*.test.mjs
node tools/performance/browser/phase_00_browser_baseline.mjs
```

It builds the operator web with the configured direct-PC origin, launches a
headed Chrome process with an isolated temporary profile, records semantic DOM
readiness after two animation frames, and cleans up only that isolated profile.
Media and WebGL scenarios stay unavailable until exact fixture selectors are
configured; shell readiness is not first-video-frame or first-3D-render evidence.

The backend service-cold runner is intentionally separate because it performs a
controlled Compose restart before every sample:

```powershell
python -m tools.performance.phase_00_service_cold_baseline
```

It restarts only `pc` service `backend`, polls the health endpoint, and then
times the first session UI request. Do not run it while operators are using the
PC API. It does not restart PostgreSQL, clear the operating-system page cache,
or claim database-cold evidence.

Dataset planning uses the production, non-persisting preflight contract:

```powershell
python -m tools.performance.phase_00_export_planning_baseline
```

Its fixture is configured at the top of the module. The semantic identity
excludes only destination free space, which can change between consecutive
requests without changing the reviewed export plan. Running an export job is
not part of this command.

## Controlled environment

Before comparing measurements, record the following metadata in both JSON reports and the phase result document:

- Git commit, operating system, Python/Node versions, dependency lockfiles, power mode, and hardware.
- Compose configuration, service image identities, database snapshot, network route, and production build mode.
- Fixture identifiers, camera count, recording duration, media sizes, and expected output identity.
- Whether the scenario is cold or warm and the exact preparation hook used to create that state.

Run baseline and candidate on the same host without unrelated workloads. Do not compare a cold result with a warm result. The harness label documents cache state; the scenario-owned `before_each` hook is responsible for actually establishing it.

## Measurement and acceptance

1. Run three warmups, then ten measured executions. Fixed-input calibration, detection, triangulation, and export jobs may use five only through the explicit approved-long-workflow configuration.
2. Retain raw samples and report median, nearest-rank p95, minimum, maximum, failures, and throughput where meaningful.
3. Pass only when controlled metadata and output identity match, required run counts are met, candidate median and p95 are each no more than 3% slower than baseline, throughput is no more than 3% lower for identical work, and candidate measured failures do not exceed baseline failures.
4. Treat changes from -3% through +3% as measurement noise. Claim an improvement only when median or p95 improves by at least 3% and the other metric does not regress beyond the gate.
5. A missing candidate scenario, an all-failed result, or an increased failure count blocks the phase.
6. Encode workflow hard limits with `maximum_p95_ms` in both baseline and candidate scenarios: Detections summary/segment latency uses `500.0`, and Stop-to-upload-init uses `5000.0`. A changed limit or a baseline/candidate result exceeding it blocks the phase.

If a result fails, capture a profile, correct the regression, and rerun both baseline and candidate under the same controls. Never overwrite a baseline with candidate results.

## Required scenarios

Each relevant phase records cold and warm results for its vertical workflow: session/overview retrieval; operator first-use; pairing/control; Stop-to-upload-init and upload throughput; preview/seek/sync/cut; calibration; detection summary/window/seek/post-processing; triangulation/3D readiness; and export planning/throughput/finalization.

## Verification command

From the repository root:

```powershell
python -m unittest discover -s tools/performance/tests -v
```
