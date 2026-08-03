# Phase 00 Performance Baseline

## Status

The reusable benchmark and comparison infrastructure is implemented and tested.
A first read-only live baseline is committed for the locally available PC and
laptop stack. Stateful jobs, true service/database cold-cache preparation,
browser first-usable rendering, and the physical device matrix remain missing;
therefore Phase 0 is still **incomplete**.

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

Environment: root commit `794e1a585e99bd4f9f015005ffa3b9ac9a662ece`, PC
runtime revision `ab9277e42086bad59804fa006bac47d09aca650c`, Windows 10.0.26200, Intel Core i9-11900K, Balanced
power mode, Docker backend at `https://127.0.0.1:5000`, and laptop proxy at
`https://127.0.0.1:9443`. Fixture: session 49, recording set 178, recordings
649-651, calibration 113, and calibration batch 114. Each available scenario
used three warmups and ten measured GET requests with stable output hashes.

| Scenario | Cache | Median ms | p95 ms | Min ms | Max ms | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Session overview UI | Header-bypass | 71.016 | 81.834 | 66.086 | 81.834 | 0 |
| Session overview UI | Warm | 74.817 | 83.579 | 70.576 | 83.579 | 0 |
| Laptop health | Warm | 5.034 | 5.571 | 4.799 | 5.571 | 0 |
| Operator HTML response | Header-bypass | 94.497 | 104.693 | 7.788 | 104.693 | 0 |
| Operator HTML response | Warm | 86.907 | 194.366 | 7.712 | 194.366 | 0 |
| Laptop-proxied session UI | Warm | 8.608 | 19.653 | 7.585 | 19.653 | 0 |
| Playback-source resolution | Warm | 30.093 | 38.374 | 28.426 | 38.374 | 0 |
| One-byte media readiness | Warm | 11.711 | 25.165 | 10.523 | 25.165 | 0 |
| Detection summary | Warm | 23.610 | 30.157 | 21.639 | 30.157 | 0 |
| First 5-second segment, 3 cameras | Warm | 70.895 | 81.547 | 61.502 | 81.547 | 0 |
| Triangulation runs metadata | Warm | 26.347 | 35.739 | 23.535 | 35.739 | 0 |
| Triangulation session status | Warm | 22.495 | 23.731 | 21.255 | 23.731 | 0 |
| Calibration viewer metadata | Warm | 28.614 | 37.758 | 24.575 | 37.758 | 0 |
| Calibration batch status | Warm | 33.912 | 38.989 | 28.771 | 38.989 | 0 |

The detection summary and segment p95 values satisfy the existing 500 ms hard
target. `Cache-Control: no-cache` is only an HTTP cache-bypass condition; it is
not represented as a true cold service, operating-system, or database cache.
Raw timing and identity evidence is in
`tools/performance/results/phase_00_live/`.

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
| Detection summary/segments/post-processing | Cold + warm | Pending | 5-10 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Summary/segment < 500 ms |
| Triangulation/3D readiness | Cold + warm | Pending | 5 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Relative gate |
| Export planning/finalization | Cold + warm | Pending | 5 each | Pending | Pending | Pending | Pending | Pending | Frames/s | Relative gate |

## Rollback

The harness is isolated under `tools/performance/` and has no runtime imports or manifest changes. Rollback consists of removing that package, its dedicated tests, and these two performance documents. No application service, schema, persisted data, or deployment configuration is affected.

## Known limitations

- Cache preparation remains workflow-owned because clearing browser, database, operating-system, and service caches requires different safe procedures.
- HTTP scenarios are read-only by design. Stateful mobile, task, and media workflows need phase-owned fixture adapters that call the same public benchmark API.
- The harness records process-level latency and supplied throughput; external profilers and resource monitors remain diagnostic tools rather than acceptance substitutes.
- The operator HTML measurement is transport readiness, not browser first-usable
  render or workflow navigation.
