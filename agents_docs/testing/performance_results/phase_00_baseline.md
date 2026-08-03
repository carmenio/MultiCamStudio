# Phase 00 Performance Baseline

## Status

The reusable benchmark and comparison infrastructure is implemented and tested.
A first read-only live baseline is committed for the locally available PC and
laptop stack, including a production browser baseline. Deterministic production
export writing and atomic finalization are also captured. Other stateful jobs,
true database cold-cache preparation, reliable multi-camera seek timing, and
the physical device matrix remain missing. Backend service-cold session
retrieval and several media-element timings are captured; therefore Phase 0 is
still **incomplete**.
All 16 committed baseline reports pass the universal self-comparison gate. A
repository-wide test now rejects missing comparison metadata, failed scenarios,
and violated hard limits in committed evidence.
This self-gate validates committed evidence integrity, not required-scenario
completeness: explicitly unavailable scenarios such as recording seek remain
phase blockers.

## Harness evidence

| Capability | Evidence | Status |
| --- | --- | --- |
| Warmup and measured runs | Enforced 3 and 10; explicit approved-long-workflow mode permits 5 measured runs | Implemented |
| Cache state | Required `cold` or `warm` label plus caller preparation hook; diagnostic `header-bypass` cannot satisfy a cold gate | Implemented |
| Latency summary | p50/median, nearest-rank p95, minimum, and maximum from raw successful samples | Implemented |
| Reliability | Warmup and measured failures retained separately | Implemented |
| Throughput | Aggregate supplied work units per aggregate measured second | Implemented |
| Regression gate | Median/p95 no more than 3% slower, throughput no more than 3% lower for identical work, and no additional measured failures | Implemented |
| Evidence completeness | Candidate run counts cannot be lower; duplicate and non-finite evidence is rejected | Implemented |
| Hard limits | Per-scenario p95 ceilings are persisted and enforced for baseline and candidate | Implemented |
| Persistence | Atomic, versioned JSON report with enforced environment, fixture, media, and output-identity equivalence | Implemented |

Focused verification command:

```powershell
python -m pytest tools/performance/tests -q
```

## Read-only live baseline

Environment: root commit `27b769e3164e5f5314fb2848bc83157b1d2af7eb`, PC
runtime revision `006267c0ee82cc5f8d9c18f61ab26773499b6f2c`, laptop
revision `33e16ddb0968a583145074310c9da72e0b1e64e1`, Windows 10.0.26200, Intel Core i9-11900K, Balanced
power mode, Docker backend at `https://127.0.0.1:5000`, and laptop proxy at
`https://127.0.0.1:9443`. Fixture: session 49, recording set 178, recordings
649-651, calibration 113, and calibration batch 114. Each available scenario
used three warmups and ten measured GET requests with stable output hashes.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Session overview UI | Header-bypass | 74.200 | 102.148 | 71.286 | 102.148 | 0 |
| Session overview UI | Warm | 74.278 | 84.993 | 64.141 | 84.993 | 0 |
| Laptop health | Warm | 7.233 | 17.596 | 5.604 | 17.596 | 0 |
| Operator HTML response | Header-bypass | 89.799 | 296.977 | 8.054 | 296.977 | 0 |
| Operator HTML response | Warm | 87.807 | 100.631 | 8.622 | 100.631 | 0 |
| Laptop-proxied session UI | Warm | 11.370 | 13.644 | 8.888 | 13.644 | 0 |
| Playback-source resolution | Warm | 39.449 | 46.629 | 37.305 | 46.629 | 0 |
| One-byte media readiness | Warm | 13.419 | 24.801 | 11.136 | 24.801 | 0 |
| Detection summary | Warm | 24.630 | 49.842 | 22.733 | 49.842 | 0 |
| First 5-second segment, 3 cameras | Warm | 79.721 | 104.998 | 68.602 | 104.998 | 0 |
| Seeked 5-second segment, 3 cameras | Header-bypass | 152.883 | 177.096 | 128.897 | 177.096 | 0 |
| Sequential 5-second segment, 3 cameras | Warm | 143.250 | 178.812 | 121.685 | 178.812 | 0 |
| Triangulation runs metadata | Warm | 26.454 | 32.690 | 22.849 | 32.690 | 0 |
| Triangulation session status | Warm | 23.286 | 33.727 | 21.750 | 33.727 | 0 |
| Calibration viewer metadata | Warm | 25.682 | 32.070 | 24.238 | 32.070 | 0 |
| Calibration batch status | Warm | 24.672 | 36.772 | 23.884 | 36.772 | 0 |
| Triangulation result retrieval, 35,815,719 bytes | Warm | 3,367.502 | 3,654.303 | 3,081.676 | 3,654.303 | 0 |

The detection summary and all three segment p95 values satisfy the existing
500 ms hard target. Segment throughput was 8,513,456 bytes/s for the first
window, 8,116,911 bytes/s for the seeked window, and 8,199,007 bytes/s for the
sequential window. Triangulation-result retrieval throughput was 10,638,163
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
| Session UI first request after backend restart | Service cold | 74.494 | 109.240 | 65.484 | 109.240 | 0 |

The run used 3 warmups and 10 measurements at root commit
`de9b1c2630a9a9d8d27f5e4a4abf00d2b19b7888` and PC revision
`24eef3ed5f4f1d0cc3795484f8d631278f2ff39b`. All 13 restarts became healthy;
median restart-to-health preparation was 5,249.595 ms. Raw evidence is in
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
| Dataset export preflight | Warm | 3,408.367 | 3,596.047 | 3,324.019 | 3,596.047 | 0 |

The run used 3 warmups and 10 measurements at root commit
`de9b1c2630a9a9d8d27f5e4a4abf00d2b19b7888` and PC revision
`24eef3ed5f4f1d0cc3795484f8d631278f2ff39b`. Every response retained semantic
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
| Export writing and atomic finalization | Warm | 2,644.353 | 2,998.632 | 2,573.341 | 2,998.632 | 0 | 14,577,767 bytes/s |

The approved long-workflow run used 3 warmups and 5 measurements at root commit
`de9b1c2630a9a9d8d27f5e4a4abf00d2b19b7888` and PC revision
`24eef3ed5f4f1d0cc3795484f8d631278f2ff39b`. Every run produced 14 artifacts
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
| Three-camera post-processing | Warm | 7,319.012 | 7,411.117 | 7,291.727 | 7,411.117 | 0 | 24,306 keypoints/s |
| Three-camera segment generation | Warm | 234.320 | 324.207 | 217.637 | 324.207 | 0 | 719,582 keypoints/s |

Each approved long-workflow scenario used 3 warmups and 5 measurements at root
commit `e11726e32c5ffc77fa19aaf50ce7ee46384245de` and PC revision
`24eef3ed5f4f1d0cc3795484f8d631278f2ff39b`. Every execution processed
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
| Three-camera fixed-fixture triangulation | Warm | 3,443.984 | 3,607.543 | 3,271.054 | 3,607.543 | 0 | 7,893 accepted 3D points/s |

The approved long-workflow run used 3 warmups and 5 measurements at root commit
`e11726e32c5ffc77fa19aaf50ce7ee46384245de` and PC revision
`24eef3ed5f4f1d0cc3795484f8d631278f2ff39b`. The fixture identity is
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
| New resumable-upload initialization | Warm | 1.730 | 1.951 | 1.374 | 1.951 | 0 | N/A |
| Interrupted-upload resume lookup | Warm | 0.490 | 0.561 | 0.456 | 0.561 | 0 | N/A |
| Four-chunk write | Warm | 50.500 | 65.447 | 47.359 | 65.447 | 0 | 323,648,678 bytes/s |
| Assembly and final checksum | Warm | 36.324 | 41.419 | 34.237 | 41.419 | 0 | 454,369,113 bytes/s |

All scenarios used 3 warmups and 10 measurements at root commit
`c0c9cc797781b653c51830477a4103b68215b75e` and PC revision
`006267c0ee82cc5f8d9c18f61ab26773499b6f2c`. The completed bytes retained SHA-256
`69bb4bc2118a3c18d925e0bb38a01f1d1e2670112c36126eb37492fca2446684`.
The server-route timing is retained as a relative baseline without the 5,000 ms
hard limit. It does **not** pass or prove the end-to-end phone
Stop-to-upload-init target, device finalization, or network latency; those
remain physical-device acceptance gaps. Raw evidence is in
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
| Four-camera metadata/readability preflight | Warm | 560.131 | 624.721 | 535.792 | 624.721 | 0 | 7.110 videos/s |
| Two-camera, 120-frame FreeMoCap solve | Warm | 29,382.152 | 29,737.110 | 29,179.373 | 29,737.110 | 0 | 8.152 camera-frames/s |

Preflight used 3 warmups and 10 measurements at root commit
`82cc86b4581dfdf5c9054a5190e654825e3cbb94`; its complete semantic identity
was `7790c0e597580ef184976de348736b8605da2b81ad30be2632eb8709807d3283`.
Processing used 3 warmups and 5 measurements at root commit
`82cc86b4581dfdf5c9054a5190e654825e3cbb94`; every execution retained TOML
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
| Ten-set, five-stage route dispatch | Warm | 0.617 | 0.915 | 0.478 | 0.915 | 0 | 76,814 tasks/s |

The run used 3 warmups and 10 measurements at root commit
`0de6323ae1ade5182a43f13467f94bb79c3624a2`. This is a controller/task-chain
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
| PC pairing-token issue | Warm | 0.328 | 0.425 | 0.264 | 0.425 | 0 | 3,001 tokens/s |
| PC pairing-token resolve | Warm | 0.289 | 0.436 | 0.264 | 0.436 | 0 | 3,281 tokens/s |

Both scenarios used 3 warmups and 10 measurements at root commit
`0de6323ae1ade5182a43f13467f94bb79c3624a2`. Normalized issue claims retained
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
| Receiver connection to relayed viewer-ready | Warm | 2.602 | 4.157 | 1.911 | 4.157 | 0 | 366 connections/s |
| Canonical device hello/status round trip | Warm | 0.700 | 0.911 | 0.572 | 0.911 | 0 | 1,374 round trips/s |
| Legacy request/device-info round trip | Warm | 0.6115 | 1.222 | 0.523 | 1.222 | 0 | 1,481 round trips/s |

All scenarios used 3 warmups and 10 measurements at root commit
`3019c02b22f9a87d7cb09542dd5ac8b4392b6f36` and laptop revision
`33e16ddb0968a583145074310c9da72e0b1e64e1`. Five normalized message hashes
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
| Ten-camera calibration viewer HTML | Warm | 0.141 | 0.236 | 0.112 | 0.236 | 0 | 67,513 cameras/s |

The run used 3 warmups and 10 measurements at root commit
`82cc86b4581dfdf5c9054a5190e654825e3cbb94` and PC revision
`7614b9d5dd7506c1295412471aa04f691ac21017`. Geometry identity was
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
| Operator first usable | Isolated cold | 321.241 | 411.761 | 294.124 | 411.761 | 0 |
| Operator first usable | Warm | 191.664 | 225.221 | 174.185 | 225.221 | 0 |
| Recordings navigation | Warm | 35.531 | 36.516 | 34.189 | 36.516 | 0 |
| Three-camera preview startup | Isolated cold | 947.208 | 1,790.330 | 517.464 | 1,790.330 | 0 |
| Primary first decoded frame | Warm | 30.400 | 41.000 | 21.600 | 41.000 | 0 |
| Three-camera synchronized playback start | Warm | 31.500 | 41.800 | 26.300 | 41.800 | 0 |
| 3D first usable WebGL render | Warm | 6,937.393 | 7,642.016 | 6,600.331 | 7,642.016 | 0 |
| 3D timeline seek readiness | Warm | 34.465 | 35.290 | 33.793 | 35.290 | 0 |
| 3D playback start | Warm | 29.428 | 30.193 | 27.917 | 30.193 | 0 |
| Calibration Plotly readiness | Warm | 863.259 | 1,340.113 | 717.428 | 1,340.113 | 0 |

The current run used root commit `9a1051063ead5441756cba16348fe435ccb3a8f9`
and laptop revision `7a18c38ea75ef700bf4c7734c6d4d403c920468d`.
The rendered shell signature hash was
`89cad48c52fc47d44b8b1e7324f6b8fb74bd6bc050694b375be0cfaba15ef0c6`.
The 3D canvas screenshot identity was
`957adae0fe64d093b9a249e4f408a84ad48ffae5746b760e465d1e2e09ec80a6`;
the calibration Plotly screenshot identity was
`73bc2b332442cd01ff43115b78f5945d8976b571783511c85e31a1bb94f7efe9`.
Raw evidence is in
`tools/performance/results/phase_00_browser/phase_00_browser_baseline.json`.
The controlled browser fixture is session 49, recording set 178, recordings
649-651. The runner resolves the exact card from backend summary ordering rather
than a display label. Multi-camera seek readiness remains unavailable:
recording 651 did not emit `seeked` within 20 seconds while recordings 649 and
650 did. All three sources reported readyState 4; the run retains each source,
current time, and outcome instead of reporting partial-camera timing. The 3D
fixture is set 178/run 100 with 11,464 timeline frames. Its first-render timer
starts at card activation and ends after a connected, non-lost WebGL canvas,
the full frame range, and two animation frames are visible. Seek uses native
browser input and accepts the rendered position within one percent of the
requested track coordinate. Calibration discovers viewer 113 through the UI,
then times its canonical viewer route until Plotly's WebGL canvas and two
animation frames are ready.

### Browser repeatability gate

The browser baseline is not yet comparison-ready even though each individual
report is internally valid. Comparing the prior controlled capture in root
commit `6cc28a1` with the current capture in `3dd2e98` on the same fixture and
with identical output hashes found cold-shell p95 4.7% slower, preview median
60.0% slower, first-frame median/p95 6.1%/8.2% slower, and Plotly p95 30.4%
slower. Other metrics improved by more than 3%. This variance exceeds the
universal acceptance band, so Phase 0 must control/profile the source of browser
timing noise and establish a repeatable pair before browser-dependent structural
work can pass. Self-comparison validates report integrity but cannot prove this
cross-run repeatability.

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
| Recording preview/seek/sync/cut | Isolated cold + warm | Session 49, set 178, recordings 649-651; five-second cut | 10 each | Preview 947.208; first frame 30.400; synchronized start 31.500; cut 6,123.213 | Preview 1,790.330; first frame 41.000; synchronized start 41.800; cut 6,380.535 | Captured | Captured | 0 | Cut 2.464 camera-seconds/s | Recording 651 seek timed out; warm local cut captured; cold cut pending |
| Pairing/control/upload | Warm local; physical devices pending | Fixed PC/Edge pairing, signaling relay, and 16 MiB/4-chunk upload fixtures | 10 each | PC issue 0.328; PC resolve 0.289; Edge issue 1.592; Edge resolve 0.552; Edge RTT 2.002; canonical RTT 0.700; legacy RTT 0.6115; upload init 1.730; chunk 50.500; completion 36.324 | PC issue 0.425; PC resolve 0.436; Edge issue 3.386; Edge resolve 1.358; Edge RTT 3.557; canonical RTT 0.911; legacy RTT 1.222; upload init 1.951; chunk 65.447; completion 41.419 | Captured | Captured | 0 | Tokens/s, round trips/s, and upload bytes/s captured | Backend init has a relative baseline only; end-to-end Stop-to-init and live nginx/TLS/QR/physical evidence pending |
| Calibration workflow | Warm | Set-201 four-camera preflight; fixed two-camera solver; fixed geometry; live viewer 113 | 10 preflight/render/browser; 5 solve | Preflight 560.131; solve 29,382.152; HTML 0.141; Plotly 863.259 | Preflight 624.721; solve 29,737.110; HTML 0.236; Plotly 1,340.113 | Captured | Captured | 0 | Videos/s, camera-frames/s, and cameras/s captured | Relative gate |
| Detection summary/segments/post-processing | Header-bypass + warm | Live: set 178/raw:1053/recordings 649-651; processing: fixed 3-camera, 1,800-frame fixture | 10 live; 5 processing | Live summary/windows captured; processing 7,319.012; generation 234.320 | Live summary/windows captured; processing 7,411.117; generation 324.207 | Captured | Captured | 0 | Live segment bytes/s plus processing/generation keypoints/s captured | Live summary/segment < 500 ms passed |
| Triangulation/3D readiness | Warm | Live: set 178/run 100; processing: fixed 3-camera, 1,800-frame calibrated fixture | 10 live; 5 processing | Render 6,937.393; seek 34.465; playback 29.428; processing 3,443.984 | Render 7,642.016; seek 35.290; playback 30.193; processing 3,607.543 | Captured | Captured | 0 | Result bytes/s plus 7,893 accepted 3D points/s | Relative gate |
| Pipeline dispatch | Warm in-process | Ten sets, five stages, deterministic adapters | 10 | 0.617 | 0.915 | 0.478 | 0.915 | 0 | 76,814 tasks/s | Worker execution pending |
| Export planning/finalization | Warm | Live preflight: session 49/set 178/run 100; writing: fixed 3-camera, 1,800-frame `two_d_3d` fixture | 10 planning; 5 writing | Planning 3,408.367; writing 2,644.353 | Planning 3,596.047; writing 2,998.632 | Planning 3,324.019; writing 2,573.341 | Planning 3,596.047; writing 2,998.632 | 0 | 14,577,767 artifact bytes/s | Relative gate |

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
- The browser runner discovers CPU, logical processor count, RAM, and Windows
  power scheme at runtime and freezes recording IDs 649-651 with coupled media
  durations/sizes. Compose hash and backend image remain SDK-style constants;
  candidate acceptance must independently confirm them.
