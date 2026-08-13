# Dataset export pipeline

## Ownership

The operator-web Export command owns a six-step draft (`Recipe`, `Selection`, `Sources`, `Ranges`, `Schema`, `Review`). The backend owns source discovery, range qualification, artifact generation, checksums, and destination safety. The shared task queue owns execution progress and cancellation. The browser never hydrates full 2D or 3D result payloads for preflight.

## Reviewed specification

Exports use one normalized specification for four recipes: `video_3d`, `video_2d`, `two_d_3d`, and `three_d_only`. Every selected set carries explicit 2D variant and/or 3D run identifiers as required by its recipe. Preflight hashes the normalized specification, destination root, result versions, 3D update version, and synchronized-file identity. Submission re-runs preflight and rejects stale hashes.

The current page publishes its ordered recording-set selection to the shell. A preserved wizard draft takes precedence until the operator uses Reset. No page selection means an empty export selection; it never expands to the full session implicitly.

Selection availability comes from the canonical All-tab overview, not from `sessions-info?profile=ui`. The UI profile intentionally omits full Detection payloads, and legacy `3D_Reconstructions` rows are not the canonical triangulation source. Workflow `stage_flags` describe how far a set has progressed; the separate `export_source_availability` flags mean that a complete per-camera Detection variant or a completed triangulation result can actually be selected for export.

Source discovery also returns recommendations without mutating the submitted specification. The operator web applies a recommendation only when a recipe-required source is unset, then repeats preflight with those explicit identifiers. A manually selected or restored source always wins. A recommended 2D source must cover every recording in the set; for `two_d_3d`, the recommendation is the newest completed 3D run with a compatible complete 2D lineage.

The Sources step stays dense by default: each recording set is a compact summary row and only one row is expanded at a time. Expanded rows own the editable source selectors, complete diagnostics, and one interactive preview workspace. A single camera selector and authoritative timeline drive every pane at 1x: Video-to-2D shows raw and 2D overlay video; Video-to-3D shows raw video, selected-camera 3D reprojection, and fused 3D; 2D-to-3D shows 2D overlay, 3D reprojection, and fused 3D; 3D-only keeps companion raw video beside reprojection and fused 3D. Companion video remains preview-only and does not change the exported recipe.

Interactive point playback uses `GET /api/exports/recording-sets/:recordingSetId/preview-segment`. The route accepts one recording, five-second segment index, and the selected immutable 2D variant and/or 3D run. It reuses canonical `keypoint_arrays_v2` rows, bounds 3D frames before serialization, returns raw `bounds` plus robust 1st-to-99th percentile `view_bounds`, and uses deterministic ETags with immutable caching. The browser loads the current window before adjacent windows, caches completed windows, and aborts obsolete work after a seek, camera/source change, or collapse. Empty current frames remain empty; a nearby populated frame is never substituted during playback.

Camera-projected 3D must use the calibration identity stored in the selected triangulation result, never the latest calibration for the set. Projection converts calibration-world metres to calibration millimetres before applying `K [R|t]`, and accepts either non-zero sign of camera depth to match triangulation reprojection. Off-image points are omitted rather than clamped, and diagnostics distinguish total, degenerate, out-of-frame, and visible points. Missing calibration or camera mapping is a non-fatal pane warning: raw video and fused 3D remain available.

Preflight chooses the earliest populated frame shared by every recipe-required point source inside the approved ranges. If no populated frame is shared, each pane uses its earliest populated in-range frame and labels that frame explicitly. Per-camera 2D samples remain compact. Source changes rerun preflight immediately, and only the newest response may replace the current preview.

## Range semantics

The base is either the full common usable timeline or merged, clamped training segments. Available frame numbers are intersected across every paired point source and synchronized-video frame counts before optional confidence qualification is applied. It considers confidence threshold, minimum duration, selected-point percentage, minimum 2D cameras, and tolerated present-but-low-quality frames. Missing source frame numbers always break continuity. For `two_d_3d`, the 2D and 3D qualifying sets are intersected and the 3D run must declare lineage to the chosen 2D variant. The reviewed range plan and probed media timing are included in the preflight fingerprint.

## Artifacts and failure behavior

Workers process one recording set and qualified range at a time. Full-range video is copied; filtered video is rendered as exact-frame CFR H.264 MP4. 2D coordinates are written in source-pixel space. 3D XYZ remains unchanged in calibration world metres, including Y; manifests record calibration-world axes, units, calibration identity, and identity translation. NPY, CSV, and JSONL are generated from the same per-range samples. Runs missing the calibration-world metadata are legacy and are neither recommended nor accepted for projection/export; operators must rerun triangulation.

Filtered video rendering requires `ffmpeg` on the backend container or host `PATH`. Preflight verifies this requirement only when the reviewed ranges require transcoding; full-range video copies do not depend on FFmpeg. Preflight also resolves every synchronized source file and performs an actual destination write probe before declaring a set eligible.

Each job writes inside a hidden temporary directory and atomically renames it on success. Cancellation or total failure removes only that temporary directory. A failed set is removed from the pending output while completed sets remain; the export result is `completed_with_warnings` unless no valid set was produced.

`manifest.json`, `manifest.sha256`, per-set `schema.json`, and `frame_map.json` provide source lineage, point order, source or overridden skeleton mapping, coordinate spaces, original/exported frame indices, serialization-independent tensor shapes, artifact paths, warnings, and SHA-256 checksums. Artifacts remain in the configured PC/server root; there is no archive or download endpoint. Completed summaries are persisted separately from Activity task rows so clearing finished Activity items does not erase export history.

## Compatibility

`POST /api/exports/session-packages` remains the synchronous compatibility surface. It preserves its request/response shape but enforces the same calibration-world requirement and exact XYZ serialization. New UI and integrations should use `/api/exports/preflight` followed by `/api/exports/jobs`.
