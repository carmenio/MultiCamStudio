# Refactor Baseline Runtime Defects

This file records defects observed while establishing the behavior-preserving
refactor baseline. They are not silently repaired inside structural commits.

## Full sessions profile exceeds the database response buffer

Observed 2026-08-03 on the controlled local stack:

```text
GET /api/sessions-info?profile=full -> HTTP 500
code: 54000
Cannot enlarge string buffer containing 1073741822 bytes by 1 more bytes.
```

The backend's full-profile query requests nested recording `Detections` rows for
the full live database. PostgREST/PostgreSQL attempts to construct a response
larger than its approximately 1 GiB string buffer. The `profile=ui` route remains
available and its baseline was captured.

Impact: the legacy full sessions response cannot currently be benchmarked or
used against this database snapshot. This is a genuine pre-existing runtime
defect, not benchmark harness failure.

Refactor rule: do not hide this result by dropping fields or changing the route
inside a structural phase. Any repair needs a separately approved behavior and
compatibility decision, with response-consumer characterization.

## Calibration metadata compatibility fallbacks

Viewer and batch-status requests return HTTP 200, but the live logs show their
newer selective PostgREST projections returning HTTP 400 before compatibility
fallback queries succeed. This adds latency and log noise. Preserve the fallback
until the live database schema and response contracts are migrated deliberately.

## Multi-camera browser seek intermittently stalls

The production-browser baseline can prepare and seek all three set-178 videos,
but repeated synchronized seeks are not reliable. On 2026-08-03 one controlled
run completed three warm-ups and three measured seeks before at least one media
element failed to emit `seeked` within 20 seconds. Other runs failed earlier.

The benchmark records the entire scenario as unavailable rather than reporting
partial-camera or partial-run timing. Preview startup, first decoded frame, and
synchronized playback-start measurements remain valid independent scenarios.
Do not loosen the all-camera readiness condition during structural refactoring;
diagnose and repair media seeking as an explicit behavior change.

## Task and All-page pipeline compatibility behavior

Characterization on 2026-08-03 confirmed several observable behaviors that may
be defects but cannot be silently changed inside structural commits:

- Invalid numeric `/api/tasks` query values return HTTP 500 rather than 400.
- All-page calibration linking is validated and recording-set links are updated
  even when the calibration stage is disabled.
- Link updates and queued task creation are not transactional. A later queue
  write failure returns HTTP 500 while earlier link and task writes remain.
- Active duplicate detection applies to sync tasks only; later stages enqueue
  another task on repeated submissions.
- When sync is disabled, an unsynced set is reported in `skipped_sets` while the
  overall request still returns HTTP 202, including when every set is skipped.
- Task database construction/probing can fall back independently in controllers
  and workers, creating a risk of separate in-memory stores after database loss.
- `TaskService.start()` silently replaces a persistent task database with a new
  in-memory store when startup orphan recovery raises, then starts normally.
  Producers may therefore continue writing persistent rows that this worker
  cannot see.
- Persistent claims inspect only the oldest 200 queued rows. An optimistic
  claim race returns no task and leaves the row queued for a later poll.
- Startup orphan recovery marks running parents as errors but does not
  immediately cascade cancellation to their queued dependents.
- Queued cancellation leaves progress at zero, while a handler cancellation
  marks progress as 100. A handler returning `None` completes with `{}`.
- The database foreign key uses `ON DELETE SET NULL`; deleting a parent can make
  a persistent child independent, unlike the fallback store's synthetic
  missing-parent cancellation behavior.
- Recording-cut cancellation is checked only at cut and recording boundaries,
  not during ffmpeg or persistence. Rollback removes partial media and persisted
  cut rows, but timing updates may already exist and an already-enqueued
  `build_recording_preview` task remains queued rather than being canceled.

The focused route tests intentionally freeze these results. Any correction needs
an explicit compatibility decision and tests for the new response and recovery
semantics.

## Triangulation test-order dependency

The triangulation controller harness previously constructed the complete Flask
application while mocking only triangulation dependencies. It passed in the
canonical suite only when earlier tests had left mocked controller imports in the
module cache; a mixed focused suite attempted live Supabase construction and
failed 21 cases. The harness now mounts `TriangulationsController` on a local
Flask app. This is a test-only repair and changes no production route behavior.
