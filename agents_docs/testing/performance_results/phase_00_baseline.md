# Phase 00 Performance Baseline

## Status

The reusable benchmark and comparison infrastructure is implemented and tested. Production workflow baselines are **not yet captured** in this document because a controlled live stack, fixed database/media snapshot, device matrix, and agreed fixture identifiers were not available to this isolated harness task. This is explicit missing acceptance evidence, not a passing application-performance result.

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

## Production baseline table

Populate this table from committed JSON evidence before Phase 1 structural changes begin.

| Scenario | Cache | Fixture | Runs | Median ms | p95 ms | Min ms | Max ms | Failures | Throughput | Hard limit |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Session/overview retrieval | Cold + warm | Pending | 10 each | Pending | Pending | Pending | Pending | Pending | N/A | Relative gate |
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
