# Detection Loading Troubleshooting

## Card says not started when results exist

The fast status route depends on `get_point_detection_set_statuses`. If the RPC
is absent, the legacy fallback must load recordings. PostgREST sees two paths
between `Recordings` and `Recording_Sets` (the direct foreign key and the
many-to-many path) and returns `PGRST201` unless the direct relationship is
qualified.

The repository query must use
`Recording_Sets!Recordings_recording_set_id_fkey!inner(session_id)`. Apply
`20260801_add_point_detection_result_segments.sql` to install the status RPC as
well. Status semantics are: finished when every current recording has a result,
partial when some do, and not started only when none do.

## Session summaries are slow

Maintained `point_detection_set_variant_summaries` rows are the fast path. Do not
load `point_detection_results.raw_result` for sets already represented there.
Legacy result reconstruction is permitted only for a set with no maintained
summary rows; applying that fallback to an entire session recreates multi-second
JSONB transfer and normalization.

## Segments are missing or slow

Check these in order:

1. Confirm the segment table and `get_point_detection_segments` RPC exist.
2. Compare distinct segmented result IDs with canonical result IDs.
3. Re-run the idempotent backfill; completed results are skipped.
4. Verify the requested `variant_key` exactly matches the canonical result.
5. Distinguish a missing segment row from a present row with `frame_count = 0`.

Do not add full-result reconstruction to the normal segment endpoint. It hides an
incomplete rollout and makes seeks scan the original large JSONB document again.

Large backfill pages can exhaust PostgREST memory because a single page may
contain several hundred megabytes of canonical JSONB. Use the script's small page
size and resume behavior instead of increasing server memory or retrying a bulk
page indefinitely.

## Post-processing fails with statement timeout 57014

Check the failing SQL in the Supabase database logs. If it inserts into
`Detections`, the worker is running an obsolete post-processing write path: new
post-processed checkpoints must be canonical-only. Restart the task worker after
deploying backend source changes so its imported controller and database modules
are refreshed.

Measure compact JSON size before changing database timeouts. Checkpoint rendering
must keep sparse changed-point `_diagnostics`, an aggregate
`postprocess.summary`, and no `postprocess.frames`. Prediction-derived
`overlay_points` must contain one catalog entry per label. A large canonical
checkpoint is inserted through `DATABASE_URL` with `RETURNING id`; do not route
it through a PostgREST representation response or restore the full legacy
duplicate.

After retrying, verify that every canonical checkpoint has its expected segment
count, `source_run_id` points to the selected raw run, and the count of legacy
`Detections` rows did not increase.
