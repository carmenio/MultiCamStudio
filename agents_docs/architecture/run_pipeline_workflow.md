# Run Pipeline workflow

## Stage registry and wizard contract

The operator-web Run Pipeline wizard derives its order, labels, icons, and initial state from `RUN_PIPELINE_STAGE_REGISTRY`. The current five stages are enabled by default to preserve Run All behavior. Every future top-level stage must explicitly set `defaultEnabled: false` until product support and tests opt it in.

The visible route is always Stage Selection, the enabled stages in registry order, then Review. Disabled stages are absent from navigation and from the submitted request. Stage configuration is one shared recipe for all selected sets and is initialized from the first selected set's saved preferences.

The modal shell owns a stationary header, scrollable tab strip, scrollable content panel, and stationary two-action footer. Phone layouts use the viewport and safe-area insets; wider layouts may use multiple field columns. Tabs use the WAI tab roles and arrow-key navigation, focus stays inside the open dialog, Escape closes it, and close restores focus to the launch control.

## Automatic recording-role discovery

`Auto-find calibration and detection sets` is an off-by-default Stage Selection option. It expands the initial set selection to every recording set in the represented sessions, forces Sync and Calibration on, and keeps the Detection, Post-Processing, and Triangulation toggles as the analysis-set recipe.

`POST /api/all-tab/run-discovery` is read-only. `RecordingSetRoleDiscovery` orders sets by `created_at` then ID, trusts completed calibrations and valid existing links, and scans only unknown sets. The bounded scan directly seeks two frames around 15%, 50%, and 85% of each camera video. Calibration requires qualifying board evidence in at least two windows on at least two cameras; zero evidence is Point Detection; partial, unreadable, insufficient-camera, conflicting, or timed-out evidence is `needs_review`. The target is about ten seconds and the hard deadline is fifteen seconds.

Review owns the final explicit assignments. Point Detection sets default to the nearest preceding Calibration set in the same session. Operators may change roles and preceding links, but submission remains blocked while any role or link is unresolved. The discovery fingerprint covers board settings, ordered set and recording metadata, and resolved media file identity (existence, size, and modified time); `/api/all-tab/run` returns `409` when that state changes after Review.

Automatic task construction is role-specific:

- Calibration: `sync_recording_set -> calibration_batch` only.
- Point Detection: `sync_recording_set` plus the enabled Detection, Post-Processing, and Triangulation stages.

All calibration sources are queued first. A following set's Sync depends on its calibration task, and each remaining stage stays in the existing per-set chain. Calibration task payloads carry their target set IDs; `linked_calibrated_set_id` is written in one PostgreSQL transaction only after calibration succeeds and before dependents become runnable. Failure, cancellation, or a link-write error therefore propagates without publishing premature or partial links. Manual mode keeps its existing request, linking, and duplicate-Sync behavior.

## Post-processing compatibility

`enabled_stages.smoothing` remains the wire compatibility key, but the user-facing stage is Post-Processing. New Run Pipeline requests send schema-v2 `post_processing` settings and queue `point_detection_postprocess`; they never create `point_detection_smoothing` tasks.

The queued post-processing task owns an immutable normalized settings snapshot. Its handler uses that snapshot when present. Dedicated or historical tasks without a snapshot continue to read the recording set's persisted preferences. Legacy `smoothing` request bodies are translated server-side into a canonical pipeline with only their smoothing method enabled.

An enabled Post-Processing stage must contain at least one active internal stage. Disabled top-level stage configuration is ignored and is not validated.

## Dependency source resolution

Point sources are resolved by the selected pipeline:

- Detection followed by Post-Processing passes the new Detection task ID as `source_run_id`.
- Triangulation after Post-Processing reads `final_variant_key` from its completed dependency task.
- Triangulation after Detection without Post-Processing uses `raw:<detection-task-id>`.
- Triangulation without either upstream stage retains the existing compatible-variant resolution behavior.

The dependency chain remains ordered per recording set. Existing duplicate Sync reuse, task cancellation, dependency failure propagation, and retained completed checkpoints are unchanged.

## Change checklist

When adding a stage or option:

1. Register the top-level stage with an explicit off-by-default declaration unless it is one of the established five compatibility stages.
2. Add options to the canonical shared definitions used by both the dedicated menu and Run Pipeline.
3. Ensure disabled configuration is omitted by the frontend and ignored by the controller.
4. Add interaction, payload, task-chain, and dependency-source tests.
5. Verify phone, tablet, and desktop layout behavior without moving the footer actions.
6. For auto-discovery changes, verify read-only scanning, stale fingerprints, editable blocking Review, role-specific task graphs, and post-success link persistence.
