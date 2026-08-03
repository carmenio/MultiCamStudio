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
