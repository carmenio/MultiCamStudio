# Phase 4: Point Detection and Post-Processing

## Status

Pending Phase 3 acceptance. No structural changes have started.

## Frozen interfaces

Catalog, raw run, summary, variant, checkpoint, diagnostics, overlay, and segment
contracts remain unchanged. Raw ownership, direct canonical checkpoint writes,
ordered stages, legacy settings aliases, sparse diagnostics, retained completed
stages, immutable five-second segments, seek cancellation, window priority,
valid unavailable windows, gzip, and ETags are non-negotiable.

## Intended ownership and data flow

Deep modules will own catalog management, run orchestration, result access,
post-processing, and streaming. Controllers and Detections views translate and
compose those workflows without reintroducing full-result playback hydration.

## Acceptance evidence required

Benchmark session summaries, first and uncached windows, sequential windows,
post-processing, and segment generation. Summary/segment p95 must remain below
500 ms. Overlay output must be equivalent to canonical results.

## Rollback

Restore existing internal callers only. No artifact, checkpoint, segment,
variant-key, task, or persisted settings migration is permitted.
