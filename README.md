# MultiCamStudio

Parent repository for the MultiCamStudio deployment split.

## Repositories

- `pc/` - `carmenio/MultiCamStudio-PC`, authoritative backend, processing, Supabase schema, task worker, model manager, and media serving.
- `laptop/` - `carmenio/MultiCamStudio-Laptop`, laptop edge stack, operator UI, phone camera app, signaling, edge relay, and proxy.

## Clone

```powershell
git clone --recurse-submodules https://github.com/carmenio/MultiCamStudio.git
cd MultiCamStudio
```

If the parent was cloned without submodules:

```powershell
git submodule update --init --recursive
```

## Commands

```powershell
npm run pc
npm run laptop
npm run pc:logs
npm run laptop:logs
```

Each child repo has its own `.env.example`; copy it to `.env` inside that child before starting its stack.

## Split PC/Laptop Networking

Run the PC backend on an address reachable from the laptop:

```env
BACKEND_HOST=0.0.0.0
BACKEND_PORT=5000
PC_BACKEND_PUBLIC_ORIGIN=https://<pc-tailscale-name-or-ip>:5000
```

From the laptop, verify the PC backend before opening the frontend:

```powershell
curl.exe -k https://<pc-tailscale-name-or-ip>:5000/health
```

For the laptop edge stack, set only the stable laptop-to-PC backend origin:
`PC_API_ORIGIN=https://<pc-tailscale-name-or-ip>:5000`. Do not save the
laptop LAN IP in `.env`; `npm run laptop` detects the active laptop LAN origin
for that run and QR links pass that origin to phones dynamically.

If you intentionally expose the laptop edge proxy through Tailscale, set
`VITE_PAIRING_TAILSCALE_ORIGIN=https://<laptop-tailnet-name-or-ip>` and enable
the laptop Tailscale pairing route. Otherwise phones should use the QR's
auto-detected LAN origin.

The Expo phone app should not be configured with `EXPO_PUBLIC_API_BASE`,
`EXPO_PUBLIC_SIGNALING_URL`, or `EXPO_PUBLIC_UPLOAD_URL`. Those values are
build-time bundle inputs; the phone app derives API, WebSocket, upload, and
certificate URLs from the scanned QR/deep link at runtime.

For direct operator-web development without the edge proxy, set
`VITE_EDGE_MODE=false` and `VITE_API_URL=https://<pc-tailscale-name-or-ip>:5000`.
Same-machine development still works with the existing localhost fallbacks.
