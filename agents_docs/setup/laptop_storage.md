# Laptop Recording Storage

The laptop edge relay stores phone and browser recordings locally before the
operator sends them to the PC. The default storage directory inside the relay is
`/data/recordings`, backed by the `laptop_edge_data` Docker volume.

## External Drive Setup

To use an external drive, set `EDGE_EXTERNAL_STORAGE_HOST_PATH` in `laptop/.env`
before starting the laptop stack.

Windows example:

```env
EDGE_EXTERNAL_STORAGE_HOST_PATH=E:\MultiCamStudioCache
```

macOS or Linux example:

```env
EDGE_EXTERNAL_STORAGE_HOST_PATH=/Volumes/Recordings/MultiCamStudioCache
```

The folder must already exist and be writable by Docker. Restart the laptop
stack after changing this value:

```bash
npm --prefix laptop run restart
```

Docker mounts the configured host path into the edge relay container at
`/external-storage`. The operator UI can then switch the active laptop recording
folder to `/external-storage` or an existing subfolder under it.

## Changing Storage During Filming

Use the filming tab right sidebar, `Laptop Storage`, to select the active
recording folder. The relay validates that the requested folder exists, is
writable, and is under an allowed storage root.

Storage changes are blocked while:

- a recording cycle is active,
- phone uploads were initialized or uploading recently,
- laptop-to-PC transfer is running.

`EDGE_STORAGE_UPLOAD_BUSY_MINUTES` controls how long a recent initialized or
uploading phone upload blocks storage changes. The default is 30 minutes, which
prevents mid-upload path changes without letting stale upload rows lock storage
forever.

Changing the active storage folder only affects new uploads. Existing cached
recordings keep their original `local_path` in SQLite and can still be played,
sent to the PC, cleared, or deleted by the normal cleanup flow.

## Operational Notes

- Keep `/data/recordings` as the fallback path; do not delete the
  `laptop_edge_data` volume unless cached laptop footage can be discarded.
- Do not expect the browser UI to browse arbitrary Windows drive letters. Docker
  must mount the host path first through `EDGE_EXTERNAL_STORAGE_HOST_PATH`.
- If the UI does not show the external storage root, confirm the `.env` value,
  restart the stack, and check the edge relay logs.
