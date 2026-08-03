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
The fixed recording-set fixture captures preview startup, first decoded frame,
and synchronized playback start. The same run loads triangulation run 100 into
the production WebGL viewer, exercises native timeline input and playback, and
loads calibration viewer 113 through its canonical Plotly route. Screenshot
hashes freeze rendered-output identity. Multi-camera recording seek remains an
explicit unavailable result when any camera misses the bounded `seeked` gate;
shell readiness is not first-video-frame or first-3D-render evidence.

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

Dataset writing and atomic finalization use the production coordinator with a
fixed three-camera `two_d_3d` fixture and in-memory persistence adapters:

```powershell
python -m tools.performance.phase_00_export_writing_baseline
```

The runner freezes the reviewed preflight before timing because planning has a
separate baseline. Each sample writes NPY, CSV, and JSONL artifacts, computes
the production checksums, writes the schema and frame map, creates the manifest,
and atomically finalizes the directory. Prior-output cleanup and post-run
manifest verification occur outside the timed interval. All files are confined
to a dedicated temporary directory and removed when the command exits.

Point-detection processing uses fixed in-memory canonical results and the
production post-processing pipeline and segmenter:

```powershell
python -m tools.performance.phase_00_detection_processing_baseline
```

The fixture has three cameras, 1,800 frames per camera, 33 points, and all six
ordered post-processing stages. Checkpoint generators are consumed stage-major,
matching controller execution. Complete output hashes are captured before and
after the timed suite; canonical JSON serialization is excluded from latency.

Triangulation processing uses the production pure service boundary with a fixed
three-camera calibrated fixture:

```powershell
python -m tools.performance.phase_00_triangulation_processing_baseline
```

Input projection and full result hashing occur outside timing. Each measured
sample triangulates the same 81,000 camera observations into 27,000 accepted 3D
points, including diagnostics and first-frame centroid transformation.

PC resumable-upload route and filesystem work uses an isolated temporary root:

```powershell
python -m tools.performance.phase_00_resumable_upload_baseline
```

This in-process runner captures initialization, interrupted-state resume,
chunk-write throughput, and assembly/final-checksum throughput. It enforces the
5,000 ms initialization ceiling as a server-side lower bound only. It is not
physical Stop-to-upload-init or radio/network evidence.

Calibration viewer generation uses a fixed database-shaped geometry row and the
production HTML renderer:

```powershell
python -m tools.performance.phase_00_calibration_viewer_baseline
```

The renderer returns its self-contained Plotly document without writing a file.
The full HTML identity is checked outside timing. This does not replace solver
or video-detection measurements; live browser Plotly readiness is captured by
the separate production browser runner.

Calibration video preflight uses the existing production OpenCV probe seam on
the four fixed set-201 videos:

```powershell
python -m tools.performance.phase_00_calibration_preflight_baseline
```

Source files are fully hashed before timing. Each warm sample reads metadata and
decodes the first frame for all cameras; it does not read every frame or claim a
cold operating-system cache.

Real calibration processing uses the production FreeMoCap runner with two
deterministic 120-frame clips prepared outside timing:

```powershell
python -m tools.performance.phase_00_calibration_processing_baseline
```

Each of three warmups and five measured solves clears only the benchmark-owned
temporary output, resets NumPy seed `20260803`, and verifies the complete TOML
and canonical result hashes. Hash verification is included in the timed work.

All-page task-chain dispatch uses the production Flask route with deterministic
in-memory persistence adapters:

```powershell
python -m tools.performance.phase_00_pipeline_dispatch_baseline
```

The fixed request dispatches all five stages for ten sets. It is a route and
task-construction lower bound; it does not measure database latency or workers.

PC pairing-token issue and resolve use the production controller and HMAC token
service with fixed camera/session adapters:

```powershell
python -m tools.performance.phase_00_pairing_baseline
```

The issue identity excludes only the volatile token expiration/signature after
cryptographic verification. Resolve freezes the complete response. These are
in-process server lower bounds, not EdgeRelay, QR, network, WebRTC, or device
measurements.

EdgeRelay pairing issue, resolve, and fresh issue-to-resolve round trip use the production Flask routes with a
single fixed camera in an isolated copy of the production SQLite schema:

```powershell
npm run benchmark:edge-pairing
```

The runner suppresses only the module's infinite transfer-worker thread,
forbids PC network calls, verifies signed token claims and the 15-minute expiry
window, and freezes the complete
resolve response including forwarded-origin API, signaling, and upload URLs.
The temporary database is removed after the report is written. This is an
in-process Edge route/cache/cryptography lower bound; it does not include nginx,
TLS/LAN, QR rendering, WebRTC, or a physical phone.

The signaling relay benchmark starts the production Node server once on an
isolated loopback port and uses real `ws` clients:

```powershell
node --test tools/performance/tests/test_phase_00_signaling_baseline.mjs
node tools/performance/phase_00_signaling_baseline.mjs
```

It measures receiver connection through relayed viewer readiness plus canonical
and legacy two-relay control round trips. Correlation IDs are normalized only
after exact message assertions. The result excludes TLS/LAN routing, WebRTC,
media, native control execution, and physical devices.

Recording cutting uses the complete production task handler with deterministic
persistence/task adapters and the backend container's production ffmpeg binary:

```powershell
python -m tools.performance.phase_00_recording_cut_baseline
```

The fixed set-178 fixture cuts seconds 60 through 65 from three synchronized
recordings. Each sample performs the real H.264 `veryfast`/96 kbps AAC
transcodes, output naming, media probing, persistence calls, progress updates,
and preview-task enqueue. Source hashing and an untimed reference run happen
before measurement; scratch-directory reset and complete output hash/probe
verification happen outside each timed interval. The runner writes only under
the verified benchmark-owned `.performance/recording-cut` root and removes all
per-run directories when it exits. It resolves the deployed container's
encoding settings and public recording origin and fails before timing if the
runner encoding differs. The measured path includes one `docker exec` launch
per camera, unlike an in-container task worker; cold-cut evidence remains
pending and must not be inferred from this warm result.

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
