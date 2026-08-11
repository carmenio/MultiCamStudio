# Dataset export pipeline

## Ownership

The operator-web Export command owns a six-step draft (`Recipe`, `Selection`, `Sources`, `Ranges`, `Schema`, `Review`). The backend owns source discovery, range qualification, artifact generation, checksums, and destination safety. The shared task queue owns execution progress and cancellation. The browser never hydrates full 2D or 3D result payloads for preflight.

## Reviewed specification

Exports use one normalized specification for four recipes: `video_3d`, `video_2d`, `two_d_3d`, and `three_d_only`. Every selected set carries explicit 2D variant and/or 3D run identifiers as required by its recipe. Preflight hashes the normalized specification, destination root, result versions, 3D update version, and synchronized-file identity. Submission re-runs preflight and rejects stale hashes.

The current page publishes its ordered recording-set selection to the shell. A preserved wizard draft takes precedence until the operator uses Reset. No page selection means an empty export selection; it never expands to the full session implicitly.

Source discovery also returns recommendations without mutating the submitted specification. The operator web applies a recommendation only when a recipe-required source is unset, then repeats preflight with those explicit identifiers. A manually selected or restored source always wins. A recommended 2D source must cover every recording in the set; for `two_d_3d`, the recommendation is the newest completed 3D run with a compatible complete 2D lineage.

The Sources step stays dense by default: each recording set is a compact summary row and only one row is expanded at a time. Expanded rows own the editable source selectors, complete diagnostics, and the lightweight 2D/3D point samples already returned by preflight. These samples are previews only; the browser must not hydrate complete result payloads. The synchronous preflight request uses an accessible indeterminate activity bar rather than a synthetic percentage.

## Range semantics

The base is either the full common usable timeline or merged, clamped training segments. Available frame numbers are intersected across every paired point source and synchronized-video frame counts before optional confidence qualification is applied. It considers confidence threshold, minimum duration, selected-point percentage, minimum 2D cameras, and tolerated present-but-low-quality frames. Missing source frame numbers always break continuity. For `two_d_3d`, the 2D and 3D qualifying sets are intersected and the 3D run must declare lineage to the chosen 2D variant. The reviewed range plan and probed media timing are included in the preflight fingerprint.

## Artifacts and failure behavior

Workers process one recording set and qualified range at a time. Full-range video is copied; filtered video is rendered as exact-frame CFR H.264 MP4. 2D coordinates are written in source-pixel space. 3D retains source units and metadata while applying the established upright Y-axis convention. NPY, CSV, and JSONL are generated from the same per-range samples.

Filtered video rendering requires `ffmpeg` on the backend container or host `PATH`. Preflight verifies this requirement only when the reviewed ranges require transcoding; full-range video copies do not depend on FFmpeg. Preflight also resolves every synchronized source file and performs an actual destination write probe before declaring a set eligible.

Each job writes inside a hidden temporary directory and atomically renames it on success. Cancellation or total failure removes only that temporary directory. A failed set is removed from the pending output while completed sets remain; the export result is `completed_with_warnings` unless no valid set was produced.

`manifest.json`, `manifest.sha256`, per-set `schema.json`, and `frame_map.json` provide source lineage, point order, source or overridden skeleton mapping, coordinate spaces, original/exported frame indices, serialization-independent tensor shapes, artifact paths, warnings, and SHA-256 checksums. Artifacts remain in the configured PC/server root; there is no archive or download endpoint. Completed summaries are persisted separately from Activity task rows so clearing finished Activity items does not erase export history.

## Compatibility

`POST /api/exports/session-packages` remains the synchronous legacy compatibility surface. New UI and integrations should use `/api/exports/preflight` followed by `/api/exports/jobs`.
