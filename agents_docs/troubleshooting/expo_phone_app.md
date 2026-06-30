# Expo Phone App Troubleshooting

## TypeScript validation command

The parent `npm --prefix laptop run typecheck:camera` command currently invokes `npx --prefix apps/camera-mobile tsc --noEmit`, which can print the TypeScript help text instead of loading the Expo app `tsconfig.json`.

Validate the Expo phone app from its own folder instead:

```powershell
cd D:\MARC\Tools\MultiCamStudio\laptop\apps\camera-mobile
npx tsc --noEmit
```

This keeps the working directory aligned with the app-level `tsconfig.json`.

## Certificate bootstrap after QR scan

The filming-tab QR should carry the laptop HTTPS origin in `api=` and the
serialized `server=` payload. The Expo app must keep using that HTTPS origin
for `/health`, pairing resolve, WebSocket signaling, and uploads.

If the iPhone has not trusted the laptop CA yet, HTTPS requests can fail before
pairing resolves. Keep the QR-derived origin in Expo state and build the public
CA download link as:

```text
http://<laptop-host>/multicam-studio-ca.cer
```

The laptop nginx proxy exposes this public certificate on HTTP port 80 so the
phone can download it before HTTPS trust exists. Do not downgrade streaming,
pairing, or upload traffic to HTTP; only the certificate download uses this
bootstrap URL.
