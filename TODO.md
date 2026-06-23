# Codex Prompt 1 — Fix Cross-Machine Frontend/Backend Connection

Fix the network communication issue between the frontend repo and backend repo. I want to ensure that the PC can talk to the Laptop and vise vera over tail scale so i can have them on differenet networks and still comunicating.

Current problem:

* Frontend and backend work when both run on the same machine.
* They fail when the frontend runs on a laptop and the backend/database runs on the PC.
* The frontend needs to pull data from the PC backend/database over the local network.

Tasks:

1. Find where backend host/port is configured.
2. Ensure the backend binds to `tailscale`, not only `localhost` or `127.0.0.1`.
3. Ensure CORS allows requests from other LAN devices.
4. Replace hardcoded localhost/frontend API URLs with configurable environment variables.
5. Add clear startup logging showing:

   * local backend URL
   * WLAN backend URL
   * port
6. Add a simple `/health` endpoint if one does not exist.
7. Update documentation or `.env.example` showing how to connect from another device.
8. Make sure the frontend can call the backend using the PC’s LAN IP.

Do not break same-machine local development.

# Codex Prompt 2 — Expo QR Code Server Discovery

Remove hardcoded IP addresses from the Expo app and replace them with QR-based server discovery. so that when i run laptop repo on another device it will be able to go from device to device without having to change and env settings.

Current problem:

* Expo app uses a constant IP address.
* When the backend PC IP changes, the app cannot connect.
* I want the QR code to include the backend machine’s connection details.

Tasks:

1. Find all hardcoded IP/backend URLs in the Expo app.
2. Replace them with a saved dynamic server config.
3. Add QR scan flow that reads backend connection info.
4. QR payload should support:

   * backend IP
   * backend port
   * protocol
   * optional server name
5. Example payload:

```json
{
  "protocol": "http",
  "host": "192.168.1.50",
  "port": 8000,
  "serverName": "MARC Backend"
}
```

6. After scanning, save the server config locally.
7. Use the saved server config for all API requests.
8. Add a connection test after scan using `/health`.
9. Show UI states:

   * Connecting
   * Connected
   * Failed to connect
10. Keep a manual fallback input for host and port.

Do not require editing source code to change IP addresses.


# Codex Prompt 3 — MultiCam Studio Fixes

Fix the MultiCam Studio workflow and UI issues.

## Run All Pipeline

Current problem:

* “Run All” stops or fails around calibration/sync.
* The pipeline needs to run smoothly and consistently.

Tasks:

1. Review the full Run All pipeline.
2. Add clear pipeline stages:

   * upload/import
   * calibration
   * sync
   * point detection
   * 3D reconstruction/viewer
3. Add UI status for each stage.
4. Add error handling so the user can see exactly what failed.
5. Add retry or resume support where reasonable.
6. Ensure the pipeline does not silently stop.
7. Add logs for each stage.

# Codex Prompt 4 — MultiCam Studio Fixes

## Multi-Select Cards

Add multi-select support to:

* recording cards
* calibration cards
* point detection cards
* 3D viewer cards

Required behaviour:

* single click select
* Shift select range
* Cmd/Ctrl click toggle selection
* Select All button
* clear selected visual state

Use a shared reusable selection helper/component if possible.


# Codex Prompt 5 — MultiCam Studio Fixes

## Remove Copy Cameras

Remove the Copy Cameras feature completely from the filming tab in the website:

* remove UI button
* remove related handlers
* remove unused backend/API logic if present
* clean up dead code

# Codex Prompt 6 — MultiCam Studio Fixes

## Filming Tab Quality Sidebar

Redesign the quality sidebar.

Controls should include:

* preset
* shutter speed
* ISO

Displayed read-only info should include:

* resolution
* capture FPS
* bitrate
* encoder
* container

Make the layout compact and easy to scan.


# Codex Prompt 7 — MultiCam Studio Fixes

## Remove Grid Aspect Ratio Controls

Remove the grid layout aspect ratio controls.
The aspect ratio should automatically match the incoming video feed.

## Upload Queue Behaviour

Current problem:

* Upload tasks remain in the queue after upload/thumbnail generation is complete.

Required behaviour:

1. Queue item should show:

   * Uploading
   * Generating preview thumbnails
   * Complete
   * Failed
2. After successful completion, remove the task from the active queue.
3. Refresh the recordings list after completion.
4. Failed tasks should remain visible with an error and retry option.

Keep the UI responsive and do not break existing upload behaviour.
