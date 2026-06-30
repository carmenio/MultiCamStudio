# Origin Routing Troubleshooting

## Laptop edge mode should keep browser API calls same-origin

For the normal split-machine deployment, the laptop operator UI should run in edge mode. In this mode, browser requests use the currently loaded laptop origin for `/api`, `/ws`, and `/upload`, and the laptop edge relay forwards backend API traffic to the PC through `PC_API_ORIGIN`.

Expected laptop-edge values:

```env
VITE_EDGE_MODE=true
PC_API_ORIGIN=https://<pc-tailnet-host>:5000
# Optional, only when the laptop edge proxy is exposed through Tailscale:
VITE_PAIRING_TAILSCALE_ORIGIN=https://<laptop-tailnet-host>
```

Do not store `LAPTOP_LAN_HOST` or `EDGE_PUBLIC_ORIGIN` in `laptop/.env` for
normal laptop deployments. Start the stack with `npm run laptop` or
`npm --prefix laptop run start`; the launcher detects the active laptop LAN IP
and sets those values only for the Docker Compose process. Use
`npm --prefix laptop run detect-ip` to preview the selected address.

`VITE_API_URL` is only for direct operator-web development when intentionally bypassing the laptop edge proxy. The direct-development combination is:

```env
VITE_EDGE_MODE=false
VITE_API_URL=https://<pc-tailnet-host>:5000
```

If browser DevTools shows a page loaded from `https://localhost/` making API requests to `https://<pc-tailnet-host>:5000/api/...`, check `VITE_EDGE_MODE` and make sure `VITE_API_URL` is not set in the frontend container. For laptop-edge deployment, recreate the laptop frontend container after changing Vite env values because the dev server reads them at startup.

For phone pairing, QR links should use the current laptop page origin when it
is not loopback. A stale configured LAN IP should not override a reachable page
origin; otherwise Expo app pairing resolves against the wrong laptop.

The Expo phone app should not depend on `EXPO_PUBLIC_API_BASE`,
`EXPO_PUBLIC_SIGNALING_URL`, or `EXPO_PUBLIC_UPLOAD_URL`. Those values are
bundled at Metro/build time and go stale when the laptop moves networks. The
QR/deep link must include the selected laptop origin in `api=` and the
serialized `server=` payload; the app derives API, WebSocket, upload, and
certificate URLs from that runtime origin.

If the request is correctly same-origin but the UI shows `No sessions yet`, inspect the `/api/sessions-info?profile=ui` response body. The `edge` object should show whether the relay refreshed from the PC or fell back to an offline cache. A failed per-session camera refresh must not discard the session list; the relay should keep the sessions and expose `edge.refresh_warning` / `edge.camera_refresh_errors` instead.
