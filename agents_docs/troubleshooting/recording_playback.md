# Recording Playback Troubleshooting

## `File unavailable` with a 502 preview response

The operator UI displays `File unavailable` after the browser's video element fails to load its resolved playback URL. For PC-generated previews, that URL uses the PC Tailscale origin and the `/preview-recordings/` route.

Check the public route with a byte-range request:

```powershell
curl.exe -sS -k -D - -o NUL -H "Range: bytes=0-0" "https://<pc-tailscale-host>/preview-recordings/recording-<id>/preview.mp4"
```

If this returns `502 Bad Gateway`, compare the active Tailscale target with the local recordings server:

```powershell
tailscale serve status
curl.exe -sS -k -D - -o NUL -H "Range: bytes=0-0" "https://127.0.0.1:8443/preview-recordings/recording-<id>/preview.mp4"
```

The PC recordings nginx container exposes HTTPS on local port `8443`. Restore the root Tailscale proxy with:

```powershell
tailscale serve --bg --yes https+insecure://127.0.0.1:8443
```

Verify that `tailscale serve status` shows the `8443` target and that the public byte-range request returns `206 Partial Content`. A service restart is not required for this routing-only repair.

Do not assume `File unavailable` means the MP4 was deleted. A stale Tailscale target can return 502 even while the file exists and the local recordings server can read it.

## Transient playback recovery

Recording tiles automatically retry the same playback URL after transient media errors. The retries are bounded to three attempts with delays of 750 ms, 1.5 seconds, and 3 seconds so a persistent missing or invalid file does not create an endless request loop.

Loading video metadata resets the retry budget. Changing the resolved playback URL cancels any pending retry and also starts with a fresh budget. Leaving the recording set cancels pending timers.

After all automatic attempts fail, the tile keeps the `File unavailable` message and shows a `Retry` button. Manual retry remounts the video immediately and starts a new bounded retry cycle. No backend request contract or stored recording path changes as part of this behavior.
