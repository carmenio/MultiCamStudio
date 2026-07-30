# Card Selection and Pending Footage

## Explorer-style card selection

Card grids on Filming, Recording, Calibration, Point Detection, and 3D use the shared ordered-selection controller.

- A checkbox toggles one card.
- A plain card-body click is inert.
- Ctrl-click or Command-click toggles one card without clearing the other selections.
- Shift-click replaces the selection with the visible range from the last anchor.
- Ctrl/Command+Shift-click adds that visible range to the current selection.
- An unmodified double-click retains the card's existing open or fullscreen behavior.
- Playback and other interactive children must not bubble into card selection.
- Select All operates on the visible filtered order and exposes checked, unchecked, and indeterminate states.
- Each page owns its selection. Hidden or removed IDs are pruned, and changing sessions resets the selection.

The contextual bar is shown only when at least one item is selected. Calibration, Point Detection, and 3D selection is organizational only and must not mutate or delete analysis results.

## Local-only pending footage deletion

Deleting pending footage never cascades between the phone, laptop, and PC.

- Phone deletion removes the upload-queue entry, the phone-local file, and its local metadata. The service must re-read the current state and reject deletion after an upload becomes active.
- Laptop deletion targets one EdgeRelay recording UUID. Verified/completed PC recordings are not exposed through this control.
- Held, paused, queued-but-not-running, and failed laptop recordings may be deleted. An uploading recording, or a queued/failed recording while the transfer worker is running, must be paused first.
- Host-storage and Docker-storage file failures must be returned as failures and must not mark the recording deleted.
- EdgeRelay cache deletion responses retain `deleted_count` and add `deleted_ids` plus `failed_ids` for partial-result handling.
- Discarding a filming finalization warning aborts only the laptop capture-cycle placeholder. Any phone copy remains untouched.

All destructive controls require explicit local-only confirmation copy. Keep per-recording actions compact and do not restore recording-set-level Clear Cache UI.
