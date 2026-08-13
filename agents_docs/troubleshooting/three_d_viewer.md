# 3D viewer troubleshooting

## Subject appears tiny or far away

Confirm the selected result declares `coordinate_space.type: calibration_world`, then inspect robust `view_bounds` rather than raw bounds. Raw triangulation bounds deliberately retain catastrophic reconstruction outliers; viewer framing must use the finite 1st-to-99th percentile whole-path bounds and move only the virtual camera.

## Saved view settings leak between recording sets

The view-settings hydration effect and persistence effect run in the same React commit. Persistence must skip that first active-set commit so stale state from the previously open set cannot overwrite the newly selected set's local-storage value before hydration applies. Keep this guard when changing 3D page state ownership.

Legacy `lockTargetToSubject` and `snapPersonToOrigin` saved values are ignored. Do not reintroduce them while sanitizing stored settings.

## Cameras or projections are missing

Use the calibration ID embedded in the selected run, not the set's latest calibration. Legacy runs intentionally return no physical cameras and must be rerun. For a compatible run, confirm camera center `-R^T t`, metre-to-millimetre projection conversion, signed non-zero depth handling, recording-to-camera mapping, and projection diagnostics.
