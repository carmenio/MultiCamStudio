# Phase 00 Performance Baseline

## Status

The reusable benchmark and comparison infrastructure is implemented and tested.
A first read-only live baseline is committed for the locally available PC and
laptop stack, including a production browser baseline. Deterministic production
export writing and atomic finalization are also captured. Other stateful jobs, true
database cold-cache preparation, media-element playback timing, and the physical
device matrix remain missing. Backend service-cold session retrieval and several
media-element timings are now captured; therefore Phase 0 is still **incomplete**.

## Harness evidence

| Capability | Evidence | Status |
| --- | --- | --- |
| Warmup and measured runs | Enforced 3 and 10; explicit approved-long-workflow mode permits 5 measured runs | Implemented |
| Cache state | Required `cold` or `warm` label plus caller preparation hook | Implemented |
| Latency summary | p50/median, nearest-rank p95, minimum, and maximum from raw successful samples | Implemented |
| Reliability | Warmup and measured failures retained separately | Implemented |
| Throughput | Aggregate supplied work units per aggregate measured second | Implemented |
| Regression gate | Median/p95 no more than 3% slower, throughput no more than 3% lower for identical work, and no additional measured failures | Implemented |
| Evidence completeness | Candidate run counts cannot be lower; duplicate and non-finite evidence is rejected | Implemented |
| Hard limits | Per-scenario p95 ceilings are persisted and enforced for baseline and candidate | Implemented |
| Persistence | Atomic, versioned JSON report with enforced environment, fixture, media, and output-identity equivalence | Implemented |

Focused verification command:

```powershell
python -m unittest discover -s tools/performance/tests -v
```

## Read-only live baseline

Environment: root commit `afc14c87f36efd778a700ee7dbf3585099af9577`, PC
runtime revision `afd9acb47ae424beadb8dd7ea54dab0c4b961343`, laptop
revision `f0df175b92f2450d8bca0a1d0b6b14451f0fa3e2`, Windows 10.0.26200, Intel Core i9-11900K, Balanced
power mode, Docker backend at `https://127.0.0.1:5000`, and laptop proxy at
`https://127.0.0.1:9443`. Fixture: session 49, recording set 178, recordings
649-651, calibration 113, and calibration batch 114. Each available scenario
used three warmups and ten measured GET requests with stable output hashes.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Session overview UI | Header-bypass | 83.281 | 115.388 | 71.859 | 115.388 | 0 |
| Session overview UI | Warm | 75.370 | 84.382 | 69.600 | 84.382 | 0 |
| Laptop health | Warm | 5.358 | 14.561 | 4.571 | 14.561 | 0 |
| Operator HTML response | Header-bypass | 48.165 | 94.470 | 7.985 | 94.470 | 0 |
| Operator HTML response | Warm | 93.264 | 106.796 | 8.099 | 106.796 | 0 |
| Laptop-proxied session UI | Warm | 9.430 | 20.586 | 7.699 | 20.586 | 0 |
| Playback-source resolution | Warm | 29.962 | 32.774 | 28.527 | 32.774 | 0 |
| One-byte media readiness | Warm | 17.309 | 23.095 | 10.882 | 23.095 | 0 |
| Detection summary | Warm | 25.791 | 36.244 | 20.894 | 36.244 | 0 |
| First 5-second segment, 3 cameras | Warm | 68.997 | 74.198 | 59.407 | 74.198 | 0 |
| Seeked 5-second segment, 3 cameras | Header-bypass | 120.823 | 131.649 | 117.102 | 131.649 | 0 |
| Sequential 5-second segment, 3 cameras | Warm | 121.818 | 139.106 | 116.963 | 139.106 | 0 |
| Triangulation runs metadata | Warm | 23.666 | 32.991 | 21.714 | 32.991 | 0 |
| Triangulation session status | Warm | 24.162 | 32.866 | 21.791 | 32.866 | 0 |
| Calibration viewer metadata | Warm | 25.430 | 38.526 | 24.146 | 38.526 | 0 |
| Calibration batch status | Warm | 25.537 | 36.633 | 24.420 | 36.633 | 0 |
| Triangulation result retrieval, 35,815,719 bytes | Warm | 3,311.008 | 3,556.172 | 3,174.850 | 3,556.172 | 0 |

The detection summary and all three segment p95 values satisfy the existing
500 ms hard target. Segment throughput was 10,482,724 bytes/s for the first
window, 10,001,669 bytes/s for the seeked window, and 9,762,334 bytes/s for the
sequential window. Triangulation-result retrieval throughput was 10,738,381
bytes/s. `Cache-Control: no-cache` is only an HTTP cache-bypass condition; it is
not represented as a true cold service, operating-system, or database cache.
Raw timing and identity evidence is in
`tools/performance/results/phase_00_live/`.

## Backend service-cold baseline

The service-cold runner restarted only the PC Compose `backend` service before
each sample, polled `/health` without touching session data, and then timed the
first `/api/sessions-info?profile=ui` request. Restart/readiness time is retained
as preparation metadata and is excluded from endpoint latency.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Session UI first request after backend restart | Service cold | 76.266 | 96.221 | 69.441 | 96.221 | 0 |

The run used 3 warmups and 10 measurements at root commit
`85c51c8a4f53d99352f2b8ccaac46999452162ce` and PC revision
`afd9acb47ae424beadb8dd7ea54dab0c4b961343`. All 13 restarts became healthy;
median restart-to-health preparation was 5,329.196 ms. Raw evidence is in
`tools/performance/results/phase_00_service_cold/phase_00_service_cold_baseline.json`.
This is service-process cold, not an operating-system page-cache or PostgreSQL
buffer-cache flush.

## Dataset export planning baseline

The export-planning runner posts a fixed `three_d_only` specification for
session 49, recording set 178, and completed triangulation run 100 to the
production preflight route. Preflight is non-persisting: it creates no job and
writes no artifacts. Semantic equivalence includes eligibility, source choices,
ranges, schema, estimated size, normalized specification, and the review hash;
only the volatile destination `free_bytes` counter is excluded from its identity.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Dataset export preflight | Warm | 3,967.282 | 4,670.150 | 3,683.326 | 4,670.150 | 0 |

The run used 3 warmups and 10 measurements at root commit
`0bfb136feebc68b5706e505e73c6c5098bc298ac` and PC revision
`afd9acb47ae424beadb8dd7ea54dab0c4b961343`. Every response retained semantic
identity `ff6712d285c531b97919d0f9c30fb881b68ad54130fff56ba2cd2630833be461`
and review hash `bcdcea8bd9fa313d4b4c895d576852a6cc7e6b81f7853aa255483f46bc3ad8b5`.
Raw evidence is in `tools/performance/results/phase_00_export_planning/`.

## Dataset export writing and finalization baseline

The writing runner uses the real `DatasetExportCoordinator` and
`DatasetExportWriter` with fixed in-memory persistence adapters. Its reviewed
fixture contains three 2D cameras plus one 3D result, 1,800 frames at 30 fps,
33 points, and NPY, CSV, and JSONL output. Preflight and prior-output cleanup are
outside the timed interval. Each sample includes artifact construction,
production SHA-256 calculation, frame-map and schema writing, manifest creation,
and atomic directory finalization.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Export writing and atomic finalization | Warm | 3,108.076 | 3,157.991 | 2,969.702 | 3,157.991 | 0 | 12,787,583 bytes/s |

The approved long-workflow run used 3 warmups and 5 measurements at root commit
`f56373e64739a29ee12a16412059d757693b6fc4` and PC revision
`ff2fad2cd05c9dc03743719214fd938d8cd8cbcf`. Every run produced 14 artifacts
and 39,288,534 artifact bytes with semantic identity
`96889e6aff65f4d037d88ad4e021d8d46a9cf69efabeae289c4e9706d03edfc9`.
The identity covers production artifact checksums and stable completion fields;
final manifest integrity is verified separately because its creation timestamp
is intentionally volatile. Raw evidence is in
`tools/performance/results/phase_00_export_writing/`.

## Detection processing and segment-generation baseline

The production pipeline processed a fixed 60-second, three-camera fixture at
30 fps with 33 points per frame. All six stages were enabled in canonical order:
confidence filtering, motion prediction, outlier rejection, PCHIP gap fill,
confidence-weighted smoothing, and rigid-body correction. The segmenter then
created 12 immutable five-second windows per camera. Fixture construction and
complete canonical output hashing were outside the timed intervals.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Three-camera post-processing | Warm | 10,498.022 | 13,876.066 | 9,067.835 | 13,876.066 | 0 | 16,567 keypoints/s |
| Three-camera segment generation | Warm | 279.237 | 421.531 | 267.706 | 421.531 | 0 | 581,695 keypoints/s |

Each approved long-workflow scenario used 3 warmups and 5 measurements at root
commit `87ef10b70ac32c99b7006a6adde4abab84e82a7f` and PC revision
`95ca0fb29f38746a4cf6d5754250af75a05f716b`. Every execution processed
178,200 input keypoints; the six stages represent 1,069,200 nominal point-stage
evaluations. Full checkpoint output retained identity
`6c7c4019c604fd66713fd15395f75ef08b6784eb83ab24077169d54a2edde1b6`,
and all 36 segments retained identity
`a3d57f5211f8e483c24d172efb1adc753e3042d5dd09b3e0d5cb8fb71a7d4db3`.
Raw evidence is in `tools/performance/results/phase_00_detection_processing/`.

## Triangulation processing baseline

The production `TriangulationService` processed a deterministic 60-second,
three-camera calibrated fixture at 30 fps with 15 connected labels. The fixture
contains 81,000 2D observations and produces 27,000 accepted 3D points. Input
projection, fixture hashing, and complete result hashing are outside the timed
operation; triangulation, diagnostics, and first-frame centroid transformation
are included.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Three-camera fixed-fixture triangulation | Warm | 4,310.144 | 4,510.427 | 3,915.031 | 4,510.427 | 0 | 6,352 accepted 3D points/s |

The approved long-workflow run used 3 warmups and 5 measurements at root commit
`e2c857c652c7457cea868e658d4d28a3b1cb1d79` and PC revision
`95ca0fb29f38746a4cf6d5754250af75a05f716b`. The fixture identity is
`3690fceccada5a27a7088259be6ec729f19d8843b6f060aa519b062d1d4e63ec`;
the complete output identity is
`a7126a69d24773083f459eb59e9764d03c6519c1387d48be4ebd37315d1a6227`.
All cameras contributed 27,000 zero-error synthetic projections, and the output
retained the applied first-frame centroid transform. Raw evidence is in
`tools/performance/results/phase_00_triangulation_processing/`.

## PC resumable-upload baseline

The real PC upload route handlers ran through an in-process Flask adapter with
fixed in-memory persistence and a dedicated temporary recording root. The
16,777,216-byte fixture uses four 4 MiB chunks. Initialization and recovery
include Flask request handling and adapter work; chunk and completion scenarios
also include production SHA-256 and filesystem operations. Fixture preparation,
cleanup, and final independent checksum verification are outside timing.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| New resumable-upload initialization | Warm | 2.019 | 2.438 | 1.526 | 2.438 | 0 | N/A |
| Interrupted-upload resume lookup | Warm | 0.511 | 0.665 | 0.463 | 0.665 | 0 | N/A |
| Four-chunk write | Warm | 58.605 | 67.493 | 54.835 | 67.493 | 0 | 277,664,628 bytes/s |
| Assembly and final checksum | Warm | 32.828 | 39.447 | 31.358 | 39.447 | 0 | 493,783,883 bytes/s |

All scenarios used 3 warmups and 10 measurements at root commit
`8f20e14b2599b5cc7a094a3e88b75902b7705332` and PC revision
`95ca0fb29f38746a4cf6d5754250af75a05f716b`. The completed bytes retained SHA-256
`69bb4bc2118a3c18d925e0bb38a01f1d1e2670112c36126eb37492fca2446684`.
The 2.438 ms initialization p95 satisfies the 5,000 ms server-side ceiling.
It does **not** prove phone Stop-to-upload-init, device finalization, or network
latency; those remain physical-device acceptance gaps. Raw evidence is in
`tools/performance/results/phase_00_resumable_upload/`.

## Calibration preflight and processing baselines

Warm video preflight calls the current production OpenCV metadata and
first-decoded-frame probes for all four set-201 videos. The source files total
418,993,355 bytes, contain 3,437 frames each at 60 fps, and are fully hashed
before timing. The real solver benchmark prepares deterministic frames 500-619
from anna and chris outside timing, then runs the production FreeMoCap boundary
with NumPy seed `20260803`.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Four-camera metadata/readability preflight | Warm | 589.459 | 678.601 | 549.929 | 678.601 | 0 | 6.660 videos/s |
| Two-camera, 120-frame FreeMoCap solve | Warm | 33,878.199 | 34,656.135 | 31,508.147 | 34,656.135 | 0 | 7.218 camera-frames/s |

Preflight used 3 warmups and 10 measurements at root commit
`80f5385fd2e6a3d3a0ec65e0243c8d3389390f7c`; its complete semantic identity
was `7790c0e597580ef184976de348736b8605da2b81ad30be2632eb8709807d3283`.
Processing used 3 warmups and 5 measurements at root commit
`2d93790d625238bdd005be0c21d8c5173e7dc19b`; every execution retained TOML
identity `3dad317eb5f84ec023039fd66d3f9f4c8dccad5dddf1c1200d2823ed544a24fc`
and canonical result identity
`ea1e323dadcb542be992c041de43f8806c1a7a5d0585596d39325cb10000035e`.
Raw evidence is under `tools/performance/results/phase_00_calibration_preflight/`
and `tools/performance/results/phase_00_calibration_processing/`.

## All-page pipeline dispatch baseline

The production `/api/all-tab/run` route dispatched a five-stage chain for ten
fixed recording sets through deterministic in-memory adapters. Each sample
created 50 ordered tasks and ten calibration batches with exact response
identity `02058072ab6f3f7f6274f6ea4e7ff5a4102e3a50e3ac17a9954f9da2023efe06`.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ten-set, five-stage route dispatch | Warm | 0.786 | 0.964 | 0.725 | 0.964 | 0 | 60,692 tasks/s |

The run used 3 warmups and 10 measurements at root commit
`eff3343b3cecb7183beaf88a460c4f2ae92db63c`. This is a controller/task-chain
construction lower bound, not database persistence or worker execution. Raw
evidence is in `tools/performance/results/phase_00_pipeline_dispatch/`.

## PC pairing-token baseline

The production PC pairing routes ran through an in-process Flask adapter with
fixed session/camera rows and the real HMAC-SHA256 token implementation. Issue
cryptographically verifies each token and freezes normalized claims while
excluding only volatile expiration/signature bytes. Resolve uses a pre-created
valid token and freezes the complete response, including recording settings.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PC pairing-token issue | Warm | 0.279 | 0.360 | 0.260 | 0.360 | 0 | 3,439 tokens/s |
| PC pairing-token resolve | Warm | 0.284 | 0.333 | 0.262 | 0.333 | 0 | 3,407 tokens/s |

Both scenarios used 3 warmups and 10 measurements at root commit
`aa531623b0a92f06d12880d74c821c643851edae`. Normalized issue claims retained
identity `c61c2901c77465676dda1f9209d3948c0d37db527c8a0beee3d97fd30f9c09e3`;
the full resolve response retained identity
`0a53d9c2aff7282ff45cb58bb76d143ebf657ea20ac56d4bd3cf8b62afe2d025`.
This is a PC route/HMAC lower bound, not EdgeRelay, QR, TLS, WebRTC, or physical
device evidence. Raw evidence is in `tools/performance/results/phase_00_pairing/`.

## EdgeRelay pairing-token baseline

The production EdgeRelay Flask issue and resolve routes ran against an isolated
SQLite cache containing one fixed session camera. The runner used the real
timed serializer, cache query, forwarded-origin URL derivation, and response
serialization while explicitly failing any attempted PC network request.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Edge pairing-token issue | Warm | 1.592 | 3.386 | 1.337 | 3.386 | 0 | 543 tokens/s |
| Edge pairing-token resolve | Warm | 0.552 | 1.358 | 0.482 | 1.358 | 0 | 1,493 tokens/s |
| Edge fresh issue-to-resolve round trip | Warm | 2.002 | 3.557 | 1.718 | 3.557 | 0 | 420 round trips/s |

All three scenarios used 3 warmups and 10 measurements at root commit
`072a6a7fd9b414f2b66c957637c6aabb4dbc7af6` and laptop revision
`f0df175b92f2450d8bca0a1d0b6b14451f0fa3e2`. The normalized issue identity is
`cc9c38241d5b629d41fcc7a0d11c3f90afb35b02ada6930a9b425a3cef212ac2`;
the complete resolve identity is
`523066633931a73ca217dba3236dd0dafe8fb4173dd2e74813cad16ee751c768`.
The raw report passes the universal comparison self-gate and is stored under
`tools/performance/results/phase_00_edge_pairing/`. This is an isolated route
lower bound, not nginx, TLS/LAN, QR, WebRTC, or physical-device evidence.

## Signaling relay baseline

The production Node signaling server ran once on an isolated unencrypted
loopback port with real `ws` clients and a benchmark-owned temporary recordings
root. Every waiter was installed before send and matched a unique correlation
ID. Exact assertions freeze `roomId`, canonical/legacy message types,
`canonicalType`, and default `protocolVersion: 2` before normalizing only the
correlation token for hashing.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Receiver connection to relayed viewer-ready | Warm | 2.138 | 2.420 | 1.790 | 2.420 | 0 | 475 connections/s |
| Canonical device hello/status round trip | Warm | 0.616 | 0.727 | 0.482 | 0.727 | 0 | 1,623 round trips/s |
| Legacy request/device-info round trip | Warm | 0.548 | 1.166 | 0.448 | 1.166 | 0 | 1,690 round trips/s |

All scenarios used 3 warmups and 10 measurements at root commit
`19434c97e4d6519b69f1db1becd3dfbaa673509c` and laptop revision
`f0df175b92f2450d8bca0a1d0b6b14451f0fa3e2`. Five normalized message hashes
are retained in the raw report. These are warm local relay lower bounds, not
TLS/LAN, WebRTC, preview, device execution, or physical control evidence. Raw
evidence is in `tools/performance/results/phase_00_signaling/`.

## Recording-cut baseline

The complete production `_cut_recording_set_task_handler` cut seconds 60
through 65 from the three synchronized set-178 recordings using the backend
container's ffmpeg binary, H.264 `veryfast`, and the production-default 96 kbps
AAC audio setting. Deterministic adapters captured the exact persistence,
progress, and preview-task contracts while all real media work remained active.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Three-camera five-second cut | Warm | 6,123.213 | 6,380.535 | 5,743.228 | 6,380.535 | 0 | 2.464 camera-seconds/s |

The run used 3 warmups and 10 measurements at root commit
`cad76dcd71564befdc93fd528437ddb3dbff12dd` and PC revision
`5c9b9088476a9a6ae4fe6326642c928c87712a0a`. Every run produced 900
frames across three five-second files and 7,414,032 output bytes. The complete
media identity is
`49750de69f7797f7a255ca26ff79ff5c61c8840aa80a8c7b4b33dc144e730ff9`;
individual file sizes, hashes, frame counts, dimensions, and durations are in
the raw report. The report passes the universal metadata/output self-gate and
freezes the deployed public recording origin. The benchmark owns and removes
only its verified scratch directories. This is warm local processing evidence
and includes per-camera `docker exec` launch overhead; it is not cold-cut,
browser seek readiness, or live database/worker evidence. Raw evidence is in
`tools/performance/results/phase_00_recording_cut/`.

## Calibration viewer generation baseline

The production database-backed renderer generated a self-contained Plotly HTML
document for ten fixed camera poses. The full 9,295-byte document and embedded
geometry were hashed outside timing; each sample includes finite-value filtering,
safe script serialization, camera data embedding, and HTML construction.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ten-camera calibration viewer HTML | Warm | 0.233 | 0.283 | 0.211 | 0.283 | 0 | 42,463 cameras/s |

The run used 3 warmups and 10 measurements at root commit
`1ec7947b88d77e6930a0c57b794041261deca60a` and PC revision
`dcb83184f2d6d5192eb15fc7435871fbdb162e91`. Geometry identity was
`e5d54c19cb958db65ac3759214131673bf132a1b1bfce2e533e64939bfd4176f`,
and complete HTML identity was
`9a7910b9c035d50c8c42b61f04f061d2db56e87bef5bffa817bb8912e7cca817`.
Raw evidence is in `tools/performance/results/phase_00_calibration_viewer/`.
Solver processing and live Plotly readiness are recorded separately above and
in the production browser section.

## Production browser baseline

The dependency-free CDP runner rebuilt the operator web with
`VITE_EDGE_MODE=false` and `VITE_API_URL=https://127.0.0.1:5000`, served the
production output on `http://127.0.0.1:4173`, and used headed Chrome at
1440 x 1000 with an isolated profile. First usable requires the shell, primary
navigation, loaded session tree, workspace, no sidebar loading state, and two
animation frames. Navigation requires `main.recording-page` plus two frames.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Operator first usable | Isolated cold | 328.012 | 390.260 | 296.474 | 390.260 | 0 |
| Operator first usable | Warm | 198.199 | 247.219 | 180.713 | 247.219 | 0 |
| Recordings navigation | Warm | 33.470 | 37.118 | 32.977 | 37.118 | 0 |
| Three-camera preview startup | Isolated cold | 880.340 | 1,148.172 | 703.461 | 1,148.172 | 0 |
| Primary first decoded frame | Warm | 28.050 | 31.700 | 23.900 | 31.700 | 0 |
| Three-camera synchronized playback start | Warm | 29.750 | 46.400 | 22.200 | 46.400 | 0 |
| 3D first usable WebGL render | Warm | 6,904.354 | 7,329.336 | 6,719.366 | 7,329.336 | 0 |
| 3D timeline seek readiness | Warm | 32.575 | 32.770 | 32.330 | 32.770 | 0 |
| 3D playback start | Warm | 29.002 | 31.417 | 27.694 | 31.417 | 0 |
| Calibration Plotly readiness | Warm | 848.624 | 978.702 | 774.550 | 978.702 | 0 |

The current run used root commit `d97f4d7720f8f15647d520d643c4bb99347b4a13`
and laptop revision `f0df175b92f2450d8bca0a1d0b6b14451f0fa3e2`.
The rendered shell signature hash was
`39b54bd26de715778c0ead6a67a50dcb98413fed488e8487d0037279c6daa2c9`.
The 3D canvas screenshot identity was
`bcc9f2c6072963e1acbbd87be6788443d187451ac66490c9d3e86fdae6ddcf6d`;
the calibration Plotly screenshot identity was
`158bdfd86032941095a4342339eed5428efad7ca910b815077b321ed7b9e8053`.
Raw evidence is in
`tools/performance/results/phase_00_browser/phase_00_browser_baseline.json`.
The controlled browser fixture is session 49, recording set 178, recordings
649-651. The runner resolves the exact card from backend summary ordering rather
than a display label. Multi-camera seek readiness remains unavailable because at
least one real media element did not emit `seeked` within 20 seconds. The run
retains that exact timeout instead of reporting partial-camera timing. The 3D
fixture is set 178/run 100 with 11,464 timeline frames. Its first-render timer
starts at card activation and ends after a connected, non-lost WebGL canvas,
the full frame range, and two animation frames are visible. Seek uses native
browser input and accepts the rendered position within one percent of the
requested track coordinate. Calibration discovers viewer 113 through the UI,
then times its canonical viewer route until Plotly's WebGL canvas and two
animation frames are ready.

`GET /api/sessions-info?profile=full` returned HTTP 500 and is intentionally
recorded unavailable. The live database rejected the nested legacy response with
PostgreSQL/PostgREST code `54000`: `Cannot enlarge string buffer containing
1073741822 bytes by 1 more bytes.` This is an existing runtime defect, documented
in `agents_docs/troubleshooting/refactor_baseline_defects.md`; it was not repaired
as part of the behavior-preserving baseline.

## Remaining production baseline table

Complete this table before Phase 1 structural changes resume.

| Scenario | Cache | Fixture | Runs | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput | Hard limit |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Session/overview retrieval | Service cold + header-bypass + warm | Session 49 | 10 each | Captured | Captured | Captured | Captured | 0 | N/A | Full profile currently 500; database cold pending |
| Recording preview/seek/sync/cut | Isolated cold + warm | Session 49, set 178, recordings 649-651; five-second cut | 10 each | Preview, first frame, and synchronized start captured; cut 6,123.213 | Preview, first frame, and synchronized start captured; cut 6,380.535 | Captured | Captured | 0 | Cut 2.464 camera-seconds/s | Seek timed out; warm local cut captured; cold cut pending |
| Pairing/control/upload | Warm local; physical devices pending | Fixed PC/Edge pairing, signaling relay, and 16 MiB/4-chunk upload fixtures | 10 each | PC issue 0.279; PC resolve 0.284; Edge issue 1.592; Edge resolve 0.552; Edge RTT 2.002; canonical RTT 0.616; legacy RTT 0.548; upload init 2.019; chunk 58.605; completion 32.828 | PC issue 0.360; PC resolve 0.333; Edge issue 3.386; Edge resolve 1.358; Edge RTT 3.557; canonical RTT 0.727; legacy RTT 1.166; upload init 2.438; chunk 67.493; completion 39.447 | Captured | Captured | 0 | Tokens/s, round trips/s, and upload bytes/s captured | Upload init < 5 s passed; live nginx/TLS/QR/physical evidence pending |
| Calibration workflow | Warm | Set-201 four-camera preflight; fixed two-camera solver; fixed geometry; live viewer 113 | 10 preflight/render/browser; 5 solve | Preflight 589.459; solve 33,878.199; HTML 0.233; Plotly 848.624 | Preflight 678.601; solve 34,656.135; HTML 0.283; Plotly 978.702 | Captured | Captured | 0 | Videos/s, camera-frames/s, and cameras/s captured | Relative gate |
| Detection summary/segments/post-processing | Header-bypass + warm | Live: set 178/raw:1053/recordings 649-651; processing: fixed 3-camera, 1,800-frame fixture | 10 live; 5 processing | Live summary/windows captured; processing 10,498.022; generation 279.237 | Live summary/windows captured; processing 13,876.066; generation 421.531 | Captured | Captured | 0 | Live segment bytes/s plus processing/generation keypoints/s captured | Live summary/segment < 500 ms passed |
| Triangulation/3D readiness | Warm | Live: set 178/run 100; processing: fixed 3-camera, 1,800-frame calibrated fixture | 10 live; 5 processing | Render 6,904.354; seek 32.575; playback 29.002; processing 4,310.144 | Render 7,329.336; seek 32.770; playback 31.417; processing 4,510.427 | Captured | Captured | 0 | Result bytes/s plus 6,352 accepted 3D points/s | Relative gate |
| Pipeline dispatch | Warm in-process | Ten sets, five stages, deterministic adapters | 10 | 0.786 | 0.964 | 0.725 | 0.964 | 0 | 60,692 tasks/s | Worker execution pending |
| Export planning/finalization | Warm | Live preflight: session 49/set 178/run 100; writing: fixed 3-camera, 1,800-frame `two_d_3d` fixture | 10 planning; 5 writing | Planning 3,967.282; writing 3,108.076 | Planning 4,670.150; writing 3,157.991 | Planning 3,683.326; writing 2,969.702 | Planning 4,670.150; writing 3,157.991 | 0 | 12,787,583 artifact bytes/s | Relative gate |

## Rollback

The harness is isolated under `tools/performance/` and adds only npm command
aliases to the root manifest. Rollback consists of removing that package, its
dedicated tests/results, the command aliases, and these performance documents.
No application service, schema, persisted data, or deployment configuration is
affected.

## Known limitations

- Cache preparation remains workflow-owned because clearing browser, database, operating-system, and service caches requires different safe procedures.
- HTTP scenarios are read-only by design. Stateful mobile, task, and media workflows need phase-owned fixture adapters that call the same public benchmark API.
- The harness records process-level latency and supplied throughput; external profilers and resource monitors remain diagnostic tools rather than acceptance substitutes.
- The operator HTML measurement is transport readiness, not browser first-usable
  render or workflow navigation.
