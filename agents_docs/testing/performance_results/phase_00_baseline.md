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

## Production browser baseline

The dependency-free CDP runner rebuilt the operator web with
`VITE_EDGE_MODE=false` and `VITE_API_URL=https://127.0.0.1:5000`, served the
production output on `http://127.0.0.1:4173`, and used headed Chrome at
1440 x 1000 with an isolated profile. First usable requires the shell, primary
navigation, loaded session tree, workspace, no sidebar loading state, and two
animation frames. Navigation requires `main.recording-page` plus two frames.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Operator first usable | Isolated cold | 312.745 | 397.122 | 298.205 | 397.122 | 0 |
| Operator first usable | Warm | 214.532 | 313.553 | 196.530 | 313.553 | 0 |
| Recordings navigation | Warm | 33.909 | 42.461 | 33.275 | 42.461 | 0 |
| Three-camera preview startup | Isolated cold | 1,012.461 | 1,351.285 | 435.312 | 1,351.285 | 0 |
| Primary first decoded frame | Warm | 28.950 | 30.700 | 21.700 | 30.700 | 0 |
| Three-camera synchronized playback start | Warm | 29.800 | 42.000 | 21.400 | 42.000 | 0 |

The current run used root commit `06e4e11dd06b313fc1cbc9a2166693e1987cdb0a`
and laptop revision `f0df175b92f2450d8bca0a1d0b6b14451f0fa3e2`.
The rendered shell signature hash was
`89cad48c52fc47d44b8b1e7324f6b8fb74bd6bc050694b375be0cfaba15ef0c6`.
Raw evidence is in
`tools/performance/results/phase_00_browser/phase_00_browser_baseline.json`.
The controlled browser fixture is session 49, recording set 178, recordings
649-651. The runner resolves the exact card from backend summary ordering rather
than a display label. Multi-camera seek readiness remains unavailable because at
least one real media element did not emit `seeked` within 20 seconds. The run
retains that exact timeout instead of reporting partial-camera timing. 3D WebGL
readiness remains unavailable until its exact visible result selector is configured.

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
| Recording preview/seek/sync/cut | Isolated cold + warm | Session 49, set 178, recordings 649-651 | 10 each | Preview, first frame, and synchronized start captured | Preview, first frame, and synchronized start captured | Captured | Captured | 0 | N/A | Seek timed out; cutting pending |
| Pairing/control/upload | Cold + warm | Pending devices | 10 each | Pending | Pending | Pending | Pending | Pending | Upload units/s | Upload init < 5 s |
| Calibration workflow | Cold + warm | Pending | 5 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Relative gate |
| Detection summary/segments/post-processing | Header-bypass + warm | Live: set 178/raw:1053/recordings 649-651; processing: fixed 3-camera, 1,800-frame fixture | 10 live; 5 processing | Live summary/windows captured; processing 10,498.022; generation 279.237 | Live summary/windows captured; processing 13,876.066; generation 421.531 | Captured | Captured | 0 | Live segment bytes/s plus processing/generation keypoints/s captured | Live summary/segment < 500 ms passed |
| Triangulation/3D readiness | Warm | Live: set 178/run 100; processing: fixed 3-camera, 1,800-frame calibrated fixture | 10 live; 5 processing | Live retrieval captured; processing 4,310.144 | Live retrieval captured; processing 4,510.427 | Captured | Captured | 0 | Result bytes/s plus 6,352 accepted 3D points/s | Browser 3D readiness pending |
| Export planning/finalization | Warm | Live preflight: session 49/set 178/run 100; writing: fixed 3-camera, 1,800-frame `two_d_3d` fixture | 10 planning; 5 writing | Planning 3,967.282; writing 3,108.076 | Planning 4,670.150; writing 3,157.991 | Planning 3,683.326; writing 2,969.702 | Planning 4,670.150; writing 3,157.991 | 0 | 12,787,583 artifact bytes/s | Relative gate |

## Rollback

The harness is isolated under `tools/performance/` and has no runtime imports or manifest changes. Rollback consists of removing that package, its dedicated tests, and these two performance documents. No application service, schema, persisted data, or deployment configuration is affected.

## Known limitations

- Cache preparation remains workflow-owned because clearing browser, database, operating-system, and service caches requires different safe procedures.
- HTTP scenarios are read-only by design. Stateful mobile, task, and media workflows need phase-owned fixture adapters that call the same public benchmark API.
- The harness records process-level latency and supplied throughput; external profilers and resource monitors remain diagnostic tools rather than acceptance substitutes.
- The operator HTML measurement is transport readiness, not browser first-usable
  render or workflow navigation.
