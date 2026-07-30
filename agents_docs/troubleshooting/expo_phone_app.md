# Expo Phone App Troubleshooting

## TypeScript validation command

The parent `npm --prefix laptop run typecheck:camera` command currently invokes `npx --prefix apps/camera-mobile tsc --noEmit`, which can print the TypeScript help text instead of loading the Expo app `tsconfig.json`.

Validate the Expo phone app from its own folder instead:

```powershell
cd D:\MARC\Tools\MultiCamStudio\laptop\apps\camera-mobile
npx tsc --noEmit
```

This keeps the working directory aligned with the app-level `tsconfig.json`.

## Slow or missing upload after Stop

The July 2026 diagnosis found that EdgeRelay received resumable uploads quickly, but the iPhone waited 55–62 seconds between the operator Stop request and `/upload/init`. The delay was phone-side: the patched shared capture controller dispatched every sample back onto its existing serial delegate queue, then synchronously waited on that queue and used an unbounded semaphore around `AVAssetWriter.finishWriting`.

The corrected contract is:

- Process sample buffers directly on the configured capture delegate queue.
- Start the finalization deadline when React Native requests Stop, mark writer inputs finished on the capture queue, and complete from a dedicated finalization queue. Never dispatch writer completion or the deadline back onto the capture queue.
- Fail finalization after 15 seconds with `SHARED_CAPTURE_RECORDING_FINALIZATION_TIMEOUT`, retain the known local recording as an error entry, and never claim that upload started.
- Persist upload entries and resumable checkpoints with serialized mutations. Queue processing must recover after a storage error, app foregrounding, or network reconnection.
- Preserve entries with invalid upload targets as blocked/error entries so the user can inspect, retry, or delete them; do not silently discard them.
- Move successful native temporary MP4s into the Documents `multicam-recordings` directory and persist only their relative locator. Absolute iOS container paths become invalid after some app rebuilds or updates.
- Resolve and preflight every local file before `/upload/init`. `LOCAL_RECORDING_FILE_MISSING` is terminal and must not retry or replace the latest recording's successful camera status.

The native probe and successful Stop result must report `implementationVersion: ios-finalization-v2`. `npm install` runs `scripts/validate-native-patch.mjs`; a missing marker means the dependency patch did not reach the native source and the build must stop. On-device, a stale or missing marker produces an explicit rebuild error instead of silently using the old stop path.

The JavaScript `NATIVE_STOP_WATCHDOG_TIMEOUT` is a secondary 17-second guard. It deliberately fires after the native 15-second deadline so native cancellation and its specific error win under normal patched builds, while still preventing an outdated or damaged native client from leaving the UI indefinitely in finalizing state.

Useful phone log timestamps are `stopRequestedAt`, `nativeFinalizedAt`, `queuedAt`, `uploadInitializedAt`, `firstByteSentAt`, and `completedAt`. The operator receives the compatible optional phase values `finalizing`, `queued`, `transferring`, and `processing`.

Because the primary correction is in `patches/react-native-webrtc+124.0.7.patch`, it requires a fresh iOS development-client or EAS build and reinstall. Metro refresh or an over-the-air JavaScript update is insufficient.

If a rebuilt app repeatedly reports `readAsStringAsync` against an old `/private/var/mobile/Containers/Data/Application/...` UUID, open Local Recordings and delete that failed historical entry. A newly successful recording must remain Ready even while the historical entry is shown as blocked.

## Finalized recording move fails with `<file>.mp4/.. is not writable`

Expo SDK 55's legacy iOS `moveAsync` checks source write permission by appending `..` to the complete file URL. For a finalized recording, this produces a non-standard path such as `<recording>.mp4/..`, which the Expo permission manager rejects even though the temporary MP4 and its parent directory are inside the app sandbox.

Keep the durable recording move behind `src/services/expoRecordingFileSystem.ts`. The adapter deliberately uses the modern `File.move` API for relocation while retaining the legacy filesystem functions for the existing metadata and directory operations. Do not replace the adapter's move implementation with `expo-file-system/legacy` `moveAsync`.

This repair is TypeScript-only because `expo-file-system` is already part of the Expo development client. Reload Metro and fully restart the app first. Rebuild the development client only if the installed client reports that the modern `File` API is unavailable. This does not replace the separate rebuild requirement for changes to the native `ios-finalization-v2` capture patch.

For acceptance, repeat at least ten recordings at the highest supported profile. Under normal LAN conditions, EdgeRelay should receive `/upload/init` within five seconds after Stop. Also interrupt Wi-Fi during one upload and confirm the persisted queue resumes without creating a duplicate recording.

If TypeScript fails inside the certificate helpers before upload code is reached, confirm `CERTIFICATE_DOWNLOAD_PATH` and `buildCertificateBootstrapUrl` are imported from `src/services/config.ts`, and ensure the certificate-origin fallback expression is assigned and closed correctly.

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
