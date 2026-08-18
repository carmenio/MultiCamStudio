# 3D viewer troubleshooting

## Subject appears tiny or far away

Confirm the selected result declares `coordinate_space.type: calibration_world`, then inspect robust `view_bounds` rather than raw bounds. Raw triangulation bounds deliberately retain catastrophic reconstruction outliers; viewer framing must use the finite 1st-to-99th percentile whole-path bounds and move only the virtual camera.

## Saved view settings leak between recording sets

The view-settings hydration effect and persistence effect run in the same React commit. Persistence must skip that first active-set commit so stale state from the previously open set cannot overwrite the newly selected set's local-storage value before hydration applies. Keep this guard when changing 3D page state ownership.

Legacy `lockTargetToSubject` and `snapPersonToOrigin` saved values are ignored. Do not reintroduce them while sanitizing stored settings.

## Cameras or projections are missing

Use the calibration ID embedded in the selected run, not the set's latest calibration. Legacy runs intentionally return no physical cameras and must be rerun. For a compatible run, confirm camera center `-R^T t`, metre-to-millimetre projection conversion, signed non-zero depth handling, recording-to-camera mapping, and projection diagnostics.

## Filmed camera is available but video is disabled

The physical pose and video linkage are separate. Confirm the calibration scene camera has a `recording_id`, then match it to the playback session stream with the same recording ID. The stream must expose a browser-playable same-origin URL. Never match camera video by its display label; names can change and are not unique identifiers.

## Video and 3D points do not align

Confirm the selected run's exact calibration supplies the complete intrinsic matrix and distortion coefficients, and that playback metadata reports the source dimensions. The viewport must use the off-axis projection rather than only vertical FOV, while the background shader applies the OpenCV radial/tangential coefficients. Check that the selected stream's offset is normalized against the playback master and that playback rate remains exactly 1.

Calibration intrinsics are immutable at their calibration resolution. When the decoded preview dimensions differ, scale `fx` and `cx` by decoded width / calibration width and scale `fy` and `cy` by decoded height / calibration height. Use that one runtime-intrinsics result for both the off-axis Three.js projection and the distortion shader. Prefer `video.videoWidth` and `video.videoHeight`, then playback metadata, then calibration dimensions; never overwrite the calibration dimensions with preview metadata.

The decoded video frame is the playback master. Use `requestVideoFrameCallback` metadata `mediaTime`, apply the normalized stream offset, map it through triangulation FPS, and clamp it to the result range. Use `requestAnimationFrame` with `currentTime` only when presented-frame callbacks are unavailable. `timeupdate` is too coarse for 60-fps skeleton playback. Seeking and paused-frame changes must synchronize immediately, and the independent skeleton timer must remain disabled while filmed-camera video is active.

At 60 fps, point meshes and skeleton lines must retain their Three.js identities. Reconcile them when labels or connections change, then update positions, visibility, confidence material colors, and line position buffers in place for each presented video frame.

## Filmed video is squashed or leaves unused space inside the camera frame

The filmed viewport is a contained rectangle with the decoded video's native aspect ratio. Observe both its available shell and the canvas container because selecting a filmed camera or entering fullscreen can change layout without a browser `resize` event. Fit the complete source rectangle inside the shell, set the renderer drawing buffer to that exact inner rectangle, and rebuild the off-axis projection immediately. The surrounding viewer may letterbox; the inner camera rectangle must not stretch, crop, or retain stale canvas dimensions. Small black wedges introduced by lens correction are expected.

If the operator has orbited or used a standard camera preset, the UI must read `Free View` and the video must be hidden. Reselect the filmed camera before evaluating alignment.

## Camera video loads from the wrong origin

Camera background media follows the laptop same-origin routing contract. Playback metadata may preserve the raw `source_url`, but the viewer must use the additive browser playback URL and normalize the known recordings, synced-recordings, preview-recordings, or adaptive-streams route through the active operator origin.
