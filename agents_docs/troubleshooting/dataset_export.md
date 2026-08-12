# Dataset export troubleshooting

## Export routes return HTML 404

The PC backend and task worker bind-mount `pc/services/backend` into their containers, but their Python processes do not reload when those files change. If a newly added export route such as `POST /api/exports/preflight` returns Flask's HTML `404 Not Found`, or the worker does not recognize `export_dataset`, first confirm that no tasks are active and restart both processes from `pc/`:

```powershell
docker compose restart backend task-worker
```

Restarting only the backend can restore the HTTP route while leaving the task worker unable to execute the submitted export. After both services restart, verify that an empty preflight request returns structured JSON validation rather than HTML 404, and confirm the worker startup log lists `export_dataset` among its registered handlers. A rebuild is unnecessary when only bind-mounted Python source changed.

## Export selection or point previews show unavailable data

Do not infer export availability from the lightweight sessions UI payload. `sessions-info?profile=ui` intentionally returns an empty `Detections` map, and `3D_Reconstructions` does not represent canonical `triangulation_runs`. Export Selection must read `export_source_availability` from `/api/all-tab/overview`; a Detection source is available only when one variant covers every recording, and a 3D source is available only when a completed run has `has_result=true`.

An eligible export can start on a frame whose point array is empty. A preview that always samples the first approved frame can therefore display "No preview points" even when thousands of later frames are populated. Keep preview sampling behind `DatasetExportCoordinator._build_preview`: prefer the earliest shared populated frame, fall back to pane-specific populated frames, and retain the approved range boundary. Set 178 with source `raw:1053` and run `100` is the regression fixture: frame 63 is empty while later frames are populated.

## Interactive Sources preview is empty, stale, or only partly available

Inspect `/api/exports/recording-sets/<set-id>/preview-segment` with the exact `recording_id`, `segment_index`, variant key, and/or run ID shown in Sources. A successful response is intentionally limited to five seconds and may contain an empty frame at the current clock position. Do not restore nearest-frame substitution or full-result browser hydration.

For missing 2D, confirm the route is returning the canonical immutable `keypoint_arrays_v2` segment for the selected variant and camera. For a missing 3D projection with fused 3D still visible, read the response warnings, then verify `result_json.input_meta.calibration_id` and that the selected recording maps into that exact calibration. Do not fall back to the latest set calibration. The response ETag varies by the complete bounded payload; after source or camera changes, confirm obsolete requests are aborted and the new cache key contains the new selection.

Both video elements are deliberately controlled by the shared Export timeline with native controls hidden. If they drift, verify both playback sources are registered in the fixed-rate synchronization profile with zero offsets and playback rate `1`; this profile corrects material drift by seeking and must never nudge playback speed. Do not add independent play buttons to individual panes. Adjacent segment prefetch is opportunistic: clamp it to known timeline bounds, do not merge its warnings into the current pane, and do not let its failure replace a successfully loaded current window.
