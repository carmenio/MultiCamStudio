# Detections Post-Processing Workflow

## Ownership

Point-detection model tasks produce raw detection artifacts only. The Detections
page owns selection of a raw source and starts one post-processing task. That
task owns every subsequent transformation; it must not call the separate legacy
smoothing task or request smoothing as part of model inference.

The Detections sidebar contains one **Post-Processing** entry. Configuration
lives in `PostProcessingDialog`, where edits remain draft-only until the
operator chooses **Save settings** or **Run Post-Processing**. Cancel, backdrop
close, and Escape discard the draft. A run always saves the canonical settings
before it submits the task.

## Ordered pipeline

Stages execute in this fixed order:

1. Confidence filtering
2. Motion prediction
3. Outlier rejection
4. Gap filling
5. Smoothing
6. Rigid-body correction

The four toggle stages execute only when enabled. Gap filling and smoothing are
exclusive method selections; `none` skips the stage. A disabled or `none` stage
does not create an artifact.

Gap filling is internal-only and never extrapolates beyond the first or last
usable observation. Every method respects `max_gap_frames`. Linear
interpolation uses the observations bounding the gap, PCHIP is shape
preserving, and cubic spline uses natural boundary conditions. Cubic spline
skips a gap and records a diagnostic reason when fewer than three usable
observations exist.

## Canonical settings

Settings are JSON and require no database migration. Schema version 2 adds the
canonical method selectors:

```json
{
  "schema_version": 2,
  "confidence_filter": { "enabled": true, "min_confidence": 0.25 },
  "motion_prediction": {
    "enabled": true,
    "model_type": "constant_velocity",
    "max_gap_frames": 15,
    "predicted_trust_score": 0.35
  },
  "outlier_rejection": {
    "enabled": true,
    "max_displacement_px": 180,
    "max_velocity_px_per_frame": 90,
    "max_acceleration_px_per_frame2": 60,
    "enable_club_length_ratio_gate": true,
    "club_head_label": "club_head",
    "club_grip_label": "club_grip",
    "club_length_min_ratio": 0.7,
    "club_length_max_ratio": 1.35
  },
  "gap_fill": { "method": "pchip", "max_gap_frames": 10 },
  "smoothing": {
    "method": "confidence_weighted",
    "params": { "alpha_min": 0.08, "alpha_max": 0.65 }
  },
  "rigid_body_correction": {
    "enabled": true,
    "stable_confidence_threshold": 0.75,
    "club_head_label": "club_head",
    "club_grip_label": "club_grip",
    "max_fill_frames_from_last_direction": 18
  }
}
```

`gap_fill.method` accepts `none`, `pchip`, `linear`, or `cubic_spline`.
`smoothing.method` accepts `none`, `confidence_weighted`, `kalman`,
`butterworth_lowpass`, `savitzky_golay`, or `moving_average`. Parameters are
method-specific and normalized by the settings PUT endpoint.

## Compatibility

The existing settings GET/PUT and run POST endpoints are retained. Responses
continue to include the deprecated `pchip_fill` and
`confidence_weighted_smoothing` aliases. Requests may also supply those aliases:

- Enabled legacy PCHIP migrates to `gap_fill.method = "pchip"`; otherwise it
  migrates to `none`.
- Enabled legacy confidence-weighted smoothing migrates to
  `smoothing.method = "confidence_weighted"`; otherwise it migrates to `none`.
- Canonical version 2 fields take precedence when canonical and deprecated
  fields are both present.

The separate smoothing endpoint and its historical metadata remain available
for Pipeline/All and older clients. New Detections work must not invoke it.

## Checkpoints and failure behavior

Each completed stage is saved immediately as an immutable result variant:

```text
postprocessed:<task-id>:<stage>
postprocessed:<task-id>:gap-fill:<method>
postprocessed:<task-id>:smoothing:<method>
```

All stage artifacts retain `variant = "postprocessed"` and use the
post-processing task ID as `run_id`. `source_variant_id` begins at the selected
raw artifact and then points to the preceding checkpoint. Optional stage,
method, order, and pipeline-run metadata allows the UI to group checkpoints
without changing existing consumers.

New post-processing checkpoints are canonical-only: persist them in
`point_detection_results`, then materialize their immutable playback segments.
Do not duplicate their full JSON into the legacy `Detections.file_path` text
column. Historical legacy rows remain readable as fallback data, and raw/model
plus legacy smoothing writes retain their compatibility behavior.

Large checkpoint inserts use the trusted backend `DATABASE_URL` connection and
`INSERT ... RETURNING id` with a 120-second statement timeout. The insert must
not travel through PostgREST's representation response because returning and
JSON-aggregating a large row can exceed the eight-second gateway role timeout.
The returned canonical ID owns segment generation. Segment storage remains
additive, so a segment failure does not delete an otherwise valid checkpoint.

Checkpoint diagnostics are sparse. A point contains `_diagnostics` only when it
was filtered/missing, predicted, rejected, gap-filled, or rigid-corrected, and
only true transformation flags plus `gap_fill_method` are retained. Aggregate
counts live in `postprocess.summary`; never restore a duplicate
`postprocess.frames` diagnostic tree. Prediction-derived `overlay_points` is a
catalog with at most one best-confidence sample per label, not a flattened copy
of every point in every frame. Canonical predictions and five-second segments
own time-varying coordinates.

If a stage fails, the task stops, reports the failed stage in progress/error
metadata, and retains checkpoints already saved. On success, the Detections
page selects the final completed checkpoint.

## UI and validation contract

The dialog uses the operator-web design tokens, shared controls, Feather icons,
focus trapping/restoration, and a bounded responsive laptop layout. Run remains
disabled when there is no raw source, no executable stage, invalid input, or an
active point-detection task. The dialog itself remains inspectable during an
active task.

The editor is a compact disclosure workflow. Stage, parameter, method, and
substage explanations are exposed from the visible label through pointer and
keyboard-accessible tooltips rather than persistent help paragraphs. Inactive
stages animate to a summary containing the stage name, an explicit off status,
and the On/Off control; collapsed controls are disabled and hidden from
assistive technology. Gap filling and smoothing map the visual Off state to
their canonical `none` method and restore the operator's last active method
when turned back on. Validation ignores inactive stage parameters and resumes
when the stage is re-enabled.

Focused coverage lives in:

- `laptop/apps/operator-web/tests/components/PostProcessingDialog.test.tsx`
- `laptop/apps/operator-web/tests/components/PointDetectionSidebar.test.tsx`
- `laptop/apps/operator-web/tests/pages/PointDetectionPage.test.tsx`
- `pc/services/backend/Tests/test_point_detection_postprocess_pipeline.py`
- `pc/services/backend/Tests/test_point_detections_controller.py`

## Detail result toolbar ownership

The Detections detail toolbar owns result viewing controls. It presents raw
detection runs as chronological `Run 1`, `Run 2`, and so on, then exposes the
selected run's raw result and every retained post-processing checkpoint in a
second output selector. Presentation ordinals never replace canonical run IDs.
Lightweight variant summaries include additive `source_run_id` and
`source_variant_id` metadata so the UI can group checkpoints without loading
canonical result JSON.

The same toolbar owns aggregate segment-hydration progress, overlay visibility,
comparison selection, searchable point/object visibility, and skeleton
visibility. View and comparison menus are portalled, viewport-clamped, and
keyboard dismissible. The right sidebar owns only model parameters, execution,
and the Post-Processing entry; do not duplicate result-view controls there.
