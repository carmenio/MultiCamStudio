# Phase 1: Recordings and Sessions

## Original responsibilities and coupling

`RecordingsController` owned route translation, five persistence adapters,
filesystem layout, upload assembly, capture finalization, task handlers, media
probing, sync/cut subprocesses, adaptive streaming, and an in-memory playback
session state machine. Constructing the controller also created external adapters
and directories before any route could be tested.

## Frozen playback-session interface

- `POST /api/playback/sessions`
- `POST /api/playback/sessions/<session_id>/join`
- `DELETE /api/playback/sessions/<session_id>`
- `GET /api/playback/sessions/<session_id>/stats`

Request validation, status codes, error strings, identifier formats, timestamps,
signaling URL precedence, stream ordering, offset aliases, duration resolution,
and response fields remain unchanged.

## First extraction

The in-memory session lifecycle now belongs to `PlaybackSessionRegistry`. Its
four-operation interface owns locking, viewer tokens, join counts, timestamps,
stream projections, deletion, and statistics. The controller retains HTTP
translation and adapts recording rows plus duration probing into the module.

Removed controller-owned duplication includes the playback dictionary, lock,
stream builder, lifecycle methods, and offset normalizer.

## Tests

A route-level characterization covers create, recording filtering, exact stream
projection, join, stats, delete, and missing-after-delete behavior. After the
extraction:

- Playback-focused Recordings tests: 10 passed.
- Full Recordings controller suite: 91 passed.
- Application worker boot suite: 6 passed.
- Python compilation passed for the controller and new module.

## Preliminary performance evidence

Environment: live local PC backend over HTTPS, unchanged database and recording
set 177, three warmups and ten measured create-session calls, with every transient
session deleted immediately.

| Metric | Before | After | Change | Gate |
| --- | ---: | ---: | ---: | --- |
| Median | 26.484 ms | 20.212 ms | 23.7% faster | Preliminary pass |
| Nearest-rank p95 | 34.277 ms | 31.336 ms | 8.6% faster | Preliminary pass |
| Failures | 0 | 0 | unchanged | Preliminary pass |

Raw samples and controlled-environment metadata are retained in
`tools/performance/results/phase_01_playback_{before,after}.json`; the automated
comparison gate passes with no context or scenario reasons.

This pair covers only the warm-cache lifecycle. The required cold-cache pair is
not yet available, so the Phase 1 performance gate and phase remain incomplete.
See `agents_docs/testing/performance_results/phase_01_recording_sessions.md`.

## Rollback

Restore the playback fields and lifecycle methods to the controller and redirect
the four routes to them. No schema, task, storage, or persisted-client migration is
needed.

## Remaining Phase 1 work

Recording upload/finalization, media preparation, synchronized playback, sync/cut
operations, and operator-web orchestration still require characterized vertical
extractions and their own benchmark evidence.
