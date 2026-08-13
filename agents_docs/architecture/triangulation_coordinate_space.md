# Triangulation coordinate-space contract

## Canonical result

New triangulation results store every XYZ sample unchanged in the calibration world frame. Calibration extrinsics are world-to-camera, calibration values are millimetres, and triangulated points are metres. A compatible result declares:

```json
{
  "coordinate_space": {
    "type": "calibration_world",
    "units": "m",
    "calibration_units": "mm",
    "translation": "identity",
    "translation_m": { "x": 0.0, "y": 0.0, "z": 0.0 },
    "calibration_id": 44
  }
}
```

Never center a result on its first frame, translate it per sequence, negate Y during export, or otherwise rewrite stored XYZ. Dataset and compatibility exports serialize XYZ exactly as stored and record the axes, units, calibration identity, and identity translation in metadata.

Runs without this metadata are legacy. They remain viewable with a warning, but are not recommended and cannot be projected or exported. Do not backfill historical payloads because their stored points may already reflect the retired centering transform; require a fresh triangulation instead.

## Viewer framing

Viewer transforms are display-only and must be applied identically to skeleton points, the grid, axes, and physical cameras. The active display basis converts world Y to viewer-up while leaving persisted/exported values unchanged.

Default, `Reset`, and `Frame Subject` target the midpoint of finite 1st-to-99th percentile bounds computed across the complete body path, with a small margin. This target is fixed while the timeline plays so walking displacement stays visible. `Frame All` expands the fit to include calibrated camera frustums. Neither action moves points.

Physical camera centers are `-R^T t` and convert from calibration millimetres to metres. Camera orientation is `R^T`; the OpenCV optical axis is positive camera Z. Camera labels and frustum intrinsics come from the exact calibration referenced by the selected run.

## Projection

Projection converts metre-valued calibration-world points back to millimetres before applying `K[R|t]`. The triangulation convention permits either sign of homogeneous camera depth, so only non-finite or effectively zero absolute depth is degenerate.

Off-image projections are omitted, never clamped to the image edge. Preview responses report total, projected, visible, degenerate, and out-of-frame counts. A non-empty source with zero visible projections must produce an actionable warning while leaving the other preview panes available.

Preview responses retain raw `bounds` for compatibility and additionally expose robust `view_bounds` for display framing. Paired previews continue to choose the earliest shared populated frame.
