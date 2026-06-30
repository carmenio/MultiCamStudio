# Laptop Host Storage Agent

The laptop host storage agent is a Flask service that runs on the laptop OS, outside Docker, and binds to `127.0.0.1:5061`.

Use it when operators need EdgeRelay to store laptop-local footage in normal host folders such as `E:\Recordings` without mounting that folder into the Docker container.

## Startup

- `npm --prefix laptop run host-storage` starts only the host storage agent in the foreground.
- `npm --prefix laptop run start` and `npm --prefix laptop run restart` start the host storage agent in the background before Docker Compose.
- EdgeRelay reaches the agent through `EDGE_HOST_STORAGE_AGENT_URL`, which defaults to `http://host.docker.internal:5061`.

The host agent must stay running while host-agent recordings are being recorded, played back, transferred to the PC, or deleted from laptop cache.

## Storage Modes

EdgeRelay supports two local storage backends:

- `docker`: the existing Docker volume or mounted `/external-storage` path.
- `host-agent`: host folder access through the laptop service.

Existing Docker-backed recordings continue to work because EdgeRelay records `storage_backend` per recording row. Host-agent recordings store the host path returned by the agent in `local_path`.

## Operator Flow

The filming sidebar calls EdgeRelay `/api/edge/storage`. When the host agent is available, the sidebar can browse host roots and child folders through `/api/edge/storage/list`, then apply a selected host path with:

```json
{ "mode": "host-agent", "path": "E:\\Recordings\\MultiCam" }
```

If the host agent is unavailable, the sidebar should show `Host storage service not running` and keep Docker storage selectable.
