# Detection Segment Streaming

## Purpose

Interactive point overlays use a read-optimized, five-second segment store. The
canonical `point_detection_results.raw_result` JSONB document remains unchanged
and continues to own exports, triangulation, auditing, and compatibility APIs.

The read model removes two expensive operations from playback: extracting every
requested window from a large JSONB document and repeatedly merging all hydrated
frames into one growing client-side array.

## Database read model

`point_detection_result_segments` contains one row per canonical result and
time-based segment. Its uniqueness key is `(point_detection_result_id,
segment_index)`. Lookup indexes also cover recording set, variant key, recording,
and segment index.

Each row stores:

- result, recording-set, recording, variant, and variant-key ownership;
- segment index, five-second start/duration, effective FPS, and frame bounds;
- total segment count and the distinction between a missing row and a valid
  empty segment;
- source dimensions, timing diagnostics, and the skeleton snapshot;
- compact `keypoint_arrays_v2` arrays, organized by point label.

Five seconds is always a time interval. Frame boundaries are calculated from the
result's effective FPS, so 30 FPS and 120 FPS recordings cover the same playback
time with different frame counts.

Canonical result writes dual-write their segments after the canonical insert.
The segment write is idempotent. If an older deployment has not applied the
segment migration, the canonical write still succeeds and logs the segment error.

## Read API

`GET /api/recording-sets/:id/point-detection/segments` accepts:

- `variant_key` (required);
- `segment_index` (required by the client, defaults to zero for compatibility);
- repeated `recording_ids` values (optional; defaults to every recording in the
  set).

One response returns the same five-second interval for all requested cameras.
It includes per-recording availability, total segment counts, timing metadata,
and compact arrays. Responses have deterministic ETags,
`Cache-Control: public, max-age=31536000, immutable`, and gzip support. Missing
recordings are named explicitly so the client can retry only missing data.

The endpoint deliberately does not reconstruct a segment from canonical JSONB.
That fallback would reintroduce the latency this read model removes. Existing
`latest`, `latest-metadata`, and `prediction-chunks` endpoints remain compatible
for older consumers.

## Operator-web scheduler

The Detections page caches compact data by recording set, variant, recording, and
segment. It renders directly from the segment containing current playback time.

Scheduling order is:

1. Segment zero for the primary variant across every video.
2. The current seek segment, then its adjacent segments.
3. Remaining segments in ascending order across every video.
4. The comparison variant after the primary variant has been prioritized.

A seek advances the request generation and aborts obsolete work. Cache keys
prevent duplicate requests and make jumps to loaded ranges immediate. A timeout
does not discard successful segments; valid empty segments are cached as complete.
Video playback is never blocked while the current overlay window is loading.

## Historical backfill

Apply `pc/infra/supabase/snippets/20260801_add_point_detection_result_segments.sql`
before running the backfill. Then execute inside the configured backend runtime:

```powershell
docker exec multicam-pc-backend-1 python -u scripts/backfill_point_detection_segments.py
```

Configuration constants are at the top of the script. Keep `PAGE_SIZE` small:
canonical results can be hundreds of megabytes and PostgREST must assemble the
selected JSON before returning it. `SKIP_COMPLETE_RESULTS` makes restarts safe,
and `AFTER_RESULT_ID` provides an explicit recovery cursor if required.

Verification queries should compare:

- canonical result count against distinct segmented result count;
- expected and actual segment counts per result;
- sampled frame numbers, labels, coordinates, confidences, and source dimensions;
- raw, smoothed, and post-processed variants, including sparse and empty windows.

## Performance checks and rollout

The diagnosed baseline was approximately 36 seconds for a session summary and
4.4 seconds for one three-camera, five-second legacy window. Before enabling the
segmented loader outside its rollout environment, benchmark the real large sets
and require:

- correct finished/partial/not-started status;
- session summaries under 500 ms;
- p95 first-window and uncached-seek responses under 500 ms on the laptop-to-PC
  path;
- sampled overlay equivalence with canonical results.

Rollout order is schema and RPCs, dual-write backend, resumable historical
backfill, equivalence/performance verification, and finally the operator-web
loader. Keep the canonical result and compatibility routes after rollout.
