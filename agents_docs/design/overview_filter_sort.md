# Overview Filter and Sort Contract

## Scope

Recordings, Calibration, Detection, and 3D overview grids use one shared filter-and-sort popover. The Feather filter icon is the far-right toolbar action and appears only while the page is showing its overview grid.

Filtering and sorting are page-local, update cards immediately, and are not persisted. Every page starts with all filters set to `Any` and creation time sorted newest first.

## Toolbar ownership

Filtering and sorting have one owner: the shared popover. A filter or sort control must never also appear inline in the toolbar or workflow sidebar. The toolbar keeps only its title, visible/total count, view controls, and workflow actions such as Add videos, Sync, Configure Detection, Link selected, and the Calibration video/camera toggle.

When a complete filtering behavior moves into the popover, remove the old control. Do not move unrelated workflow behavior merely because it is near a filter.

## Interaction and accessibility

- The icon has an accessible page-specific name and displays the number of active filters.
- The popover is portalled, clamped to the viewport, and stacks fields on narrow screens.
- Select fields have visible and accessible group labels. Changes apply immediately with AND semantics across filter groups.
- Click-away and Escape close the popover. Escape restores focus to the trigger.
- Reset all restores `Any` filters and newest-first sorting.
- The toolbar summary remains `X of Y sets`.
- If filtering hides selected cards, ordered Explorer selection is reconciled to the remaining visible card order.

## Shared ordering

Every overview supports created time, canonical name, video count, total canonical source size, and usable set length in both directions. Workflow overviews also support attention-first status ordering: error, running, queued, partial, done, then not started.

Unknown duration and size values always sort last. Equal values use creation time newest first and then set ID descending for deterministic output.

## Summary metadata

`GET /api/sessions-info` retains `Recording_Sets` and adds `Recording_Set_Summaries`. Each summary contains the set ID, canonical set name, creation/update time, sync state, video count, usable duration, and total source size.

Usable duration is the shortest recording for synced sets and the longest recording for unsynced sets. It is unknown if any required duration is missing. Total size is unknown unless every canonical source recording has `size_bytes` metadata. All card types use the canonical name and fall back to `Recording Set {id}`.

Detection post-processing presence and 3D persisted-result presence must come from lightweight summary/status queries; overview rendering must not hydrate full result payloads.
