# Phase 1: Recording and Session Performance

## Status

Incomplete. The initial playback-session slice has a controlled warm-cache
before/after pair, but the required cold-cache pair and the remaining recording
workflow scenarios have not been measured. These numbers must not be used to
claim Phase 1 acceptance.

## Environment and fixture

- Source commits: PC `ca5c9848201524771f26ed7a1ffcadc15fcdc98e`
  before and `cb1353e3b6d3f1e19d24ac181190bc100528b4ed` after.
- Hardware: Intel Core i9-11900K, 68,595,343,360 bytes RAM, Windows build
  10.0.26200, Balanced power mode.
- Route: `https://localhost:5000` to the Docker-published backend port.
- Fixture: session 49, recording set 177, recordings 646-648, three cameras.
- Cache preparation: three unmeasured create/delete lifecycle requests.
- Runs: three warmups and ten measurements per implementation.
- Resolved runtime versions:
  `tools/performance/environments/phase_01_backend_pip_freeze.txt`.

## Warm-cache results

| Scenario | Metric | Before | After | Change | Slice gate |
| --- | --- | ---: | ---: | ---: | --- |
| Playback session create | Median | 26.484 ms | 20.212 ms | 23.7% faster | Pass |
| Playback session create | Nearest-rank p95 | 34.277 ms | 31.336 ms | 8.6% faster | Pass |
| Playback session create | Failures | 0 | 0 | unchanged | Pass |

Raw evidence is in
`tools/performance/results/phase_01_playback_before.json` and
`tools/performance/results/phase_01_playback_after.json`. Both reports preserve
the source commit and the expected response identity hash.

## Missing acceptance evidence

- Cold-cache playback-session measurements.
- Recording-set loading, preview startup, seek readiness, synchronization, and
  cutting measurements.
- Browser first-frame and synchronized playback scenarios.

Until these are present, the universal 3% phase gate is not satisfied.
