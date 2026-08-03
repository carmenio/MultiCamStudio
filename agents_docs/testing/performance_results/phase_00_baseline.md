# Phase 00 Performance Baseline

## Status

The reusable benchmark and comparison infrastructure is implemented and tested.
A first read-only live baseline is committed for the locally available PC and
laptop stack, including a production browser baseline. Stateful jobs, true
service/database cold-cache preparation, media-element playback timing, and the
physical device matrix remain missing; therefore Phase 0 is still **incomplete**.

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

## Production browser baseline

The dependency-free CDP runner rebuilt the operator web with
`VITE_EDGE_MODE=false` and `VITE_API_URL=https://127.0.0.1:5000`, served the
production output on `http://127.0.0.1:4173`, and used headed Chrome at
1440 x 1000 with an isolated profile. First usable requires the shell, primary
navigation, loaded session tree, workspace, no sidebar loading state, and two
animation frames. Navigation requires `main.recording-page` plus two frames.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Operator first usable | Isolated cold | 304.414 | 314.121 | 292.143 | 314.121 | 0 |
| Operator first usable | Warm | 198.080 | 198.664 | 181.214 | 198.664 | 0 |
| Recordings navigation | Warm | 33.409 | 46.880 | 32.734 | 46.880 | 0 |

The run used root commit `4175bee9540d7b1a74b71cf7fc5ab15344c59f4e`
and laptop revision `6257c61274b700262e781c58507cce257f9232fd`.
The rendered shell signature hash was
`89cad48c52fc47d44b8b1e7324f6b8fb74bd6bc050694b375be0cfaba15ef0c6`.
Raw evidence is in
`tools/performance/results/phase_00_browser/phase_00_browser_baseline.json`.
Preview startup, first video frame, seeking, synchronization, and 3D WebGL
readiness remain explicit unavailable scenarios until their fixture selectors
are configured.

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
| Session/overview retrieval | True cold + warm | Session 49 | 10 each | Header-bypass/warm captured | Header-bypass/warm captured | Captured | Captured | 0 | N/A | Full profile currently 500 |
| Recording preview/seek/sync/cut | Cold + warm | Pending | 10 each | Pending | Pending | Pending | Pending | Pending | Where applicable | Relative gate |
| Pairing/control/upload | Cold + warm | Pending devices | 10 each | Pending | Pending | Pending | Pending | Pending | Upload units/s | Upload init < 5 s |
| Calibration workflow | Cold + warm | Pending | 5 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Relative gate |
| Detection summary/segments/post-processing | Header-bypass + warm | Set 178, raw:1053, recordings 649-651 | 10 each | Summary and three segment cases captured | Summary and three segment cases captured | Captured | Captured | 0 | Segment bytes/s captured | Summary/segment < 500 ms passed; post-processing pending |
| Triangulation/3D readiness | Warm | Set 178, run 100 | 10 | Metadata/status/result retrieval captured | Metadata/status/result retrieval captured | Captured | Captured | 0 | Result bytes/s captured | Processing and browser 3D readiness pending |
| Export planning/finalization | Cold + warm | Pending | 5 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Relative gate |

## Rollback

The harness is isolated under `tools/performance/` and has no runtime imports or manifest changes. Rollback consists of removing that package, its dedicated tests, and these two performance documents. No application service, schema, persisted data, or deployment configuration is affected.

## Known limitations

- Cache preparation remains workflow-owned because clearing browser, database, operating-system, and service caches requires different safe procedures.
- HTTP scenarios are read-only by design. Stateful mobile, task, and media workflows need phase-owned fixture adapters that call the same public benchmark API.
- The harness records process-level latency and supplied throughput; external profilers and resource monitors remain diagnostic tools rather than acceptance substitutes.
- The operator HTML measurement is transport readiness, not browser first-usable
  render or workflow navigation.
