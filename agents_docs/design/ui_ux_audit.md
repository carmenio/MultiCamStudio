# MultiCamStudio UI/UX Audit

Status: approved design baseline  
Audit date: 30 July 2026  
Surfaces: laptop operator web and Expo camera companion  
Audience: product owner, designers, and implementers

## Executive summary

MultiCamStudio already exposes most of the capabilities required for capture,
review, calibration, point detection, 3D processing, and export. Its main UX
problem is not missing functionality; it is that navigation, operational
status, task controls, configuration, diagnostics, and maintenance commands are
presented with nearly equal visual weight.

The operator interface behaves like three applications compressed into one
window: a project browser, a workflow navigator, and a context inspector. On a
1920-pixel display this is dense but usable. At 1366 x 768 the two sidebars take
enough space that the camera or recording workspace stops being visually
dominant. The filming inspector becomes a long form whose first screen mixes
recording, storage infrastructure, camera-copy tooling, quality, and grid
layout.

The phone app has a similar problem in a different form. Its intended routine
journey is scan, connect, preview, and record, but the initial setup screen gives
certificate probes, server configuration, raw origins, pairing-token handling,
and diagnostics first-class prominence. Source inspection also found complete
gallery, full-screen camera-control, and diagnostics renderers that are not
reachable from the rendered `setup | live` navigation.

The recommended direction is a task-oriented shell:

- Left pane: projects, sessions, recording sets, and task activity.
- Top navigation: workflow stages only.
- Center: the selected task and its primary actions.
- Right pane: properties of the selected object, not global administration.
- Settings and troubleshooting: infrequent configuration, maintenance, and
  infrastructure details.
- Phone: a short pairing flow, a camera-first live surface, reachable local
  recordings, and secondary settings/diagnostics.

The highest priority is state reliability. During the live audit, collapsing
the panes on the All screen left the center workspace saying `No sessions yet`
while the project tree still contained sessions. Layout changes must never
discard or reinterpret loaded data.

## Scope and method

The audit combined:

- Live inspection of all six operator workflows at wide and 1366 x 768 laptop
  viewports.
- Expanded and collapsed left/right pane states.
- DOM and accessible-name inspection of navigation, controls, status, and
  errors.
- Source review of operator page components, shared sidebars, CSS breakpoints,
  the Expo `App.tsx`, and the native recording/upload contracts.
- Comparison with current [Fluent navigation](https://fluent2.microsoft.design/components/web/react/core/nav/usage),
  [Carbon UI shell](https://carbondesignsystem.com/components/UI-shell-left-panel/usage/),
  [Apple sidebar](https://developer.apple.com/design/human-interface-guidelines/sidebars),
  [Apple tab bar](https://developer.apple.com/design/human-interface-guidelines/tab-bars),
  and [WCAG 2.2 target-size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)
  guidance.

Phone findings are source- and contract-backed because an installed native Expo
development client was not attached to this Windows audit environment. They
must be visually confirmed on iOS and Android during Phase 3.

## Evidence

The captured images show the inspected build, not redesign mockups.

### Filming at laptop width

![Filming at 1366 by 768](assets/ui_ux_audit/operator-filming-1366x768.jpg)

At this size, project navigation and the expanded inspector leave a narrow
center column. The right pane exposes storage health, storage root, subfolder,
refresh/apply, copy cameras, quality, and grid settings before the operator can
reach the rest of the form. The canvas is no longer the visual center of the
capture workflow.

### Collapsed shell state

![All screen with both sidebars collapsed](assets/ui_ux_audit/operator-all-collapsed.jpg)

The collapsed left rail uses the same folder glyph for every session, so the
icons are indistinguishable without hovering. More importantly, this captured
state shows `No sessions yet` after the panes were collapsed even though the
expanded project tree had loaded sessions immediately before the transition.

Additional evidence is stored in
[`agents_docs/design/assets/ui_ux_audit`](assets/ui_ux_audit/README.md):

- `operator-filming-wide.jpg`
- `operator-recording.jpg`
- `operator-calibration.jpg`
- `operator-point-detection.jpg`
- `operator-3d-viewer.jpg`
- `operator-all-pipeline.jpg`

## Severity model

| Severity | Meaning | Expected response |
| --- | --- | --- |
| Critical | Data, state, or action feedback contradicts the system and can cause an operator to make an unsafe decision. | Fix before visual restructuring. |
| High | A frequent task is confusing, error-prone, hidden, or materially constrained. | Include in the next workflow release. |
| Medium | The issue adds cognitive load or inconsistency but has a clear workaround. | Correct while touching the owning surface. |
| Low | Polish, wording, or consistency improvement with limited workflow risk. | Include in the design-system/polish phase. |

## Proposed information architecture

### Operator shell

| Region | Owns | Must not own |
| --- | --- | --- |
| Left project pane | Search, new session, session/recording-set hierarchy, selection, compact task activity | Page settings, export configuration, camera quality, storage forms |
| Top workflow navigation | Pipeline, Capture, Recordings, Calibration, Detection, 3D | Page commands or object actions |
| Center workspace | Current content, empty/loading/error state, page toolbar, primary action, selected item | Persistent global settings |
| Right inspector | Properties and actions for the current page or selected object | Unrelated maintenance and server configuration |
| Global settings | Storage, camera defaults, cache management, connectivity, export presets, troubleshooting | High-frequency capture and analysis actions |

Recommended label changes:

- `All` -> `Pipeline` or `Overview`.
- `Filming` -> `Capture`.
- `Recording` -> `Recordings`.
- `Point Detection` -> `Detection` when space is constrained; keep the full
  accessible name.
- `3D Viewer` -> `3D` in the compact top navigation, with `3D workspace` as the
  page title.

These are workflow stages, so their order should remain stable. Icons may be
added for faster scanning, but text labels stay visible in the normal desktop
state. Fluent explicitly advises against an unfamiliar icon-only navigation
layout; compact icon rails require tooltips and accessible names.

### Phone navigation

1. Pairing/onboarding: scan the QR, request permissions, show progress, connect.
2. Camera: preview, connection/recording state, camera source, and the few live
   controls that need immediate access.
3. Recordings: local files, upload state, retry, playback, and local delete.
4. Settings/diagnostics: camera defaults, certificate repair, manual server,
   raw diagnostics, and build/runtime information.

Camera and Recordings are top-level destinations after pairing. Settings is a
toolbar action or sheet, not a peer tab. During first use, certificate setup is
shown only when the trust check proves it is required.

## Cross-cutting findings

| ID | Severity | Finding | User impact | Recommendation | Acceptance criteria |
| --- | --- | --- | --- | --- | --- |
| UX-001 | Critical | Pane collapse/resize can leave Pipeline/All reporting no sessions while the project tree still has sessions. | The operator cannot trust whether content exists and may create duplicates or abandon work. | Decouple pane visual state from sessions and selection state; preserve the last valid dataset through transitions. | Repeatedly collapse/expand both panes at all supported widths without changing loaded session counts, selected session, expanded tree nodes, or Pipeline rows. |
| UX-002 | High | Three persistent navigation/control regions compete with the workspace. | Capture and review content becomes secondary, especially at laptop width. | Apply the ownership model above and introduce explicit wide, compact, and overlay shell states. | The center workspace keeps at least 60% of width at 1366 px with one inspector open; opening a second pane uses an overlay or closes the other pane. |
| UX-003 | High | Right inspectors mix frequent actions with setup, diagnostics, and maintenance. | Operators scan long forms and can change unrelated settings during live work. | Keep contextual properties in the inspector; move infrastructure and maintenance to Settings or overflow dialogs. | The first inspector viewport contains the current state and primary task controls only. |
| UX-004 | High | Raw `Failed to fetch` messages appear without service, consequence, recovery, or cached-state information. | The same message can mean storage, transfer, playback, sessions, or analysis failure. | Use a shared error-state component with service label, retained content, retry, timestamp, and troubleshooting disclosure. | Every surfaced network error identifies what failed, what remains usable, and one next action. |
| UX-005 | High | Loading, empty, offline, and error states are visually similar blank regions. | Users cannot tell whether to wait, configure, retry, or create content. | Define distinct state components and reserve blank space for genuinely empty content. | Each data surface has documented loading, empty, cached/offline, partial, and failure fixtures. |
| UX-006 | High | High-frequency commands are sometimes separated from the objects they affect. | Users must look between center toolbar, right inspector, and global header to complete one task. | Put record, sync, retry, run, and review actions in the page/object toolbar; reflect them in the inspector only when they edit properties. | One primary action is visible next to the affected content in every normal workflow state. |
| UX-007 | High | The compact project rail repeats the same folder icon for every session. | Collapsing saves space but destroys recognition and forces tooltip-by-tooltip inspection. | Show initials/date tokens or thumbnail/status distinctions, selected treatment, and informative tooltips; consider a temporary flyout list on activation. | A user can identify the selected session and open any other session without expanding the permanent pane. |
| UX-008 | Medium | Active states rely heavily on subtle dark-purple border/fill changes. | Current location and selected cards are hard to distinguish on dark displays. | Increase contrast and combine color with a shape, marker, check, or label. | Active/focus/selected/disabled states remain distinguishable in grayscale and meet non-text contrast requirements. |
| UX-009 | Medium | Duplicate headings consume space without adding orientation (`3D Viewer / 3D Viewer`, `Capture Controls / Filming`). | The interface feels denser and hierarchy is unclear. | Use one page/pane title plus an optional selected-object subtitle. | No pane repeats the same concept in adjacent title and subtitle fields. |
| UX-010 | Medium | Typography is very small and frequently uppercase. The 1366 filming audit found 25 visible text elements below 12 px. | Labels and status values are hard to scan at distance and at 200% zoom. | Establish type tokens; use at least 12 px for auxiliary desktop text and 14 px for normal controls, with uppercase reserved for short category labels. | No essential label or state depends on sub-12 px text; reflow works at 200% zoom. |
| UX-011 | Medium | 43 of 45 visible filming controls at 1366 x 768 were below the preferred 44 px touch dimension. | Laptop touchscreens and imprecise pointer use are unnecessarily difficult. | Use 32/36 px dense desktop controls only where pointer-first density is essential; use 44 px for primary/touch-relevant controls and maintain WCAG spacing. | Automated checks meet WCAG 24 x 24 minimum; primary actions and mobile controls meet 44 x 44. |
| UX-012 | Medium | Icons are inconsistent: some important actions are icon-only, while many secondary actions are full-width text buttons. | Visual priority follows component choice rather than task importance. | Create one icon set and button hierarchy: primary, secondary, quiet, icon, and destructive. | Every icon-only action has a tooltip and accessible name; button style maps consistently to action priority. |
| UX-013 | Medium | Maintenance actions such as clear cache receive permanent, prominent placement. | Rare actions distract from routine work and can appear safer or more necessary than they are. | Put maintenance commands in a page overflow or Settings > Storage and cache. | Maintenance is reachable in two interactions but absent from the default task inspector. |
| UX-014 | Medium | Status is fragmented across badges, free text, task panels, transfer bars, and inspectors. | Users must assemble system state mentally and may miss a blocker. | Define shared semantic states and a compact activity center for uploads, tasks, warnings, and completion. | The same state uses the same label, color, icon, and ARIA announcement everywhere. |
| UX-015 | Medium | Responsive behavior mostly shrinks/scrolls the existing shell rather than changing composition. | Narrow windows preserve every control at the cost of the task canvas. | Add width-and-height-aware shell breakpoints and overlay drawers. | Supported viewports have no hidden primary action, clipped navigation, or unusably narrow media canvas. |
| UX-016 | Low | Sentence case, title case, abbreviations, and technical names are mixed. | The product feels less coherent and increases interpretation time. | Adopt sentence case for actions/labels, nouns for destinations, verbs for commands, and a controlled glossary. | Copy review finds no competing labels for the same state or operation. |

## Screen-by-screen findings

### Shared shell and project tree

1. **High — The project pane combines navigation and task monitoring.** The task
   summary occupies permanent footer space even when it is `0/0`. Replace it
   with an activity icon and badge; open a flyout or right-side activity center
   when work exists.
2. **Medium — Session rows lack useful secondary identity.** Counts are present,
   but date, status, current stage, and recent activity are absent. Show one
   concise secondary line or badges only when they distinguish sessions.
3. **Medium — The top navigation is centered independently of the workspace.**
   It can look detached when panes change width. Anchor the workflow bar to the
   center workspace, not the full application frame.
4. **Medium — Export is an unlabeled icon separated at the far right.** Keep the
   icon in a workspace command bar, show a tooltip, and expose `Export` as text
   when space allows.
5. **Low — `Project Tree` describes a widget, not the user's content.** Prefer
   `Sessions` or the active project name.

### Pipeline / All

1. **Critical — Layout state can contradict session state.** Track as UX-001 and
   fix before redesign.
2. **High — The name `All` does not explain the screen.** Rename it `Pipeline`
   or `Overview` and state what can be done there.
3. **High — Dense rows prioritize IDs and repeated `Synced` badges over stage
   progression.** Each recording set should show a compact stage path:
   Recorded -> Synced -> Calibrated -> Detected -> 3D, with the first blocker
   and available next action.
4. **High — Selection mode, Run, collapse, and per-row overflow are cryptic.**
   Use a labeled batch toolbar that appears after selection, shows the selection
   count, previews enabled stages, and names the run action.
5. **Medium — The queue pane is empty but permanently consumes width.** Collapse
   it to an activity button when empty and open it automatically only for new
   failures or user-requested inspection.

### Filming / Capture

1. **High — The live camera grid is not protected as the primary surface.** At
   1366 px the project and inspector panes dominate. Default the project pane to
   compact while capturing and allow the inspector to overlay or auto-collapse.
2. **High — Recording is visually equal to settings and recovery controls.** Use
   a persistent capture toolbar with a large Record/Stop control, duration,
   armed camera count, storage readiness, and one blocker summary.
3. **High — Storage setup is embedded in the capture inspector.** Show only
   readiness, free space, and active destination. Open a storage dialog for
   mode/root/subfolder changes.
4. **High — `Copy Cameras` is unrelated to an active capture.** Move it to the
   session overflow menu or camera management dialog.
5. **Medium — Quality exposes derived technical output as a form.** Use named
   presets in the routine path; place shutter, bitrate, resolution, encoder, and
   container details under Advanced.
6. **Medium — The laptop-footage panel permanently occupies center space even
   when empty.** Convert it into an activity tray that expands when transfers
   exist or fail.
7. **Medium — Camera cards repeat unavailable metrics.** Hide absent FPS,
   resolution, latency, and dropped-frame fields until a signal exists; use the
   space for a clear connection state and recovery action.

### Recordings

1. **High — Recording-set cards have large empty preview regions.** When a
   thumbnail is unavailable, replace the blank rectangle with compact metadata,
   camera count, duration, sync state, and a clear open action.
2. **High — Sync actions are duplicated between the page toolbar and right
   inspector.** Keep `Sync recordings` next to the open set; let the inspector
   own manual offset properties only when manual mode is active.
3. **High — `File unavailable` and `Failed to fetch` appear as separate raw
   failures.** Present one recording-level recovery panel and preserve other
   playable cameras.
4. **Medium — `Clear video cache` is a persistent peer to sync.** Move it to
   overflow/Settings and describe scope and consequences before execution.
5. **Medium — Empty media space and a zero-duration timeline look like a broken
   player.** Show a deliberate unavailable/loading state with per-camera retry
   and routing diagnostics under disclosure.

### Calibration

1. **High — Set cards communicate only `Not linked` without the next step.** Add
   the blocker, required source, and contextual `Link calibration` action.
2. **Medium — The top filter count and right-side include toggle are separated.**
   Put set count, filter, sort, and include-unsynced controls in one collection
   toolbar above the cards.
3. **Medium — `Video view / Camera view` is page display mode, not an inspector
   property.** Move it to the page toolbar as a segmented control.
4. **Medium — The default card imagery is blank.** Use a representative frame,
   camera mosaic, or compact no-preview state rather than a silent dark block.

### Point Detection

1. **High — `Not started` cards do not expose model readiness or the next
   action.** Show prerequisite state, selected model, and `Run detection` after
   one or more cards are selected.
2. **High — The raw `Failed to fetch` banner does not identify whether model,
   task, or recording data failed.** Apply UX-004 and retain loaded cards.
3. **Medium — `Include uncalibrated` is enabled without explaining the quality
   implication.** Use a filter with warning copy and remember the preference.
4. **Medium — Model management should be a setup surface.** Routine detection
   should choose a model/preset; installation and service diagnostics belong in
   Settings.

### 3D workspace

1. **High — The right inspector opens many nested controls by default.** Start
   with View and the next required pipeline action; collapse camera coordinates,
   subject alignment, scene configuration, triangulation details, and training
   segments until relevant.
2. **High — Numeric camera controls dominate before a 3D result exists.** When
   triangulation has not run, prioritize prerequisites and `Run 3D`; reveal
   view tuning after results load.
3. **Medium — Several toggles display only `On` or `Off` in identical button
   shapes.** Use switches or checkboxes with persistent labels and clear state.
4. **Medium — Presets and raw position fields appear at the same level.** Keep
   Front/Side/Top/Iso/Reset visible; put X/Y/Z/target/FOV under Advanced camera.
5. **Medium — Training segment controls are mixed with visualization and
   triangulation.** Treat training selection as a distinct mode with its own
   toolbar and timeline instructions.

### Export and dialogs

1. **High — Export is a large multi-step workflow launched from a small icon.**
   Open a named wizard from the Pipeline or 3D toolbar, preserve progress, and
   summarize scope before creation.
2. **Medium — Advanced point mapping and connections appear in the same modal
   system as simple selection.** Use clear steps, step titles, back navigation,
   validation at the owning field, and a final review page.
3. **Medium — Dialog sizing should be tested at 1366 x 768 and 200% zoom.** The
   footer actions must remain visible and focus must stay within the modal.

### Expo camera companion

Source: `laptop/apps/camera-mobile/App.tsx`.

1. **Critical — Implemented destinations are unreachable.** `activeScreen` is
   limited to `setup | live`; the root renders only those two screens. The
   camera tab, full-screen control screen, media tab, settings tab, and tab-bar
   styles are not connected to navigation. This makes local recordings and
   diagnostics discoverable only through code, not the product.
2. **High — Setup is a long technical form instead of an onboarding state
   machine.** Replace it with four visible steps: Scan, Permissions, Trust when
   required, Connected. Show one primary action and progressive status.
3. **High — Certificate internals are permanently exposed.** URLs, probe
   origins, multiple repeated certificate lines, and manual instructions belong
   in conditional repair guidance after an actual trust failure.
4. **High — Manual server configuration is too prominent.** Keep it under
   Advanced troubleshooting and prefill it from the QR-derived origin.
5. **High — Live preview overlays contain many small metrics and controls.** Keep
   connection, REC, duration, storage/upload warning, camera switch, and
   essential exposure controls. Put bitrate and pipeline diagnostics in a
   details sheet.
6. **High — Recordings must be a reachable first-class destination.** The
   existing playback, retry/send, progress, and local delete behaviors should
   become a Recordings screen without changing their storage or upload
   contracts.
7. **Medium — Custom modal and custom navigation patterns ignore native
   conventions.** Move to Expo Router stacks, native tabs, and form sheets where
   compatible with the custom development-client requirements.
8. **Medium — Dense 9-12 px labels and 32-36 px actions are too small for a
   phone used around camera equipment.** Use Dynamic Type-compatible text,
   tabular numbers for counters, and 44 x 44 minimum targets.
9. **Medium — Important error/status text is not consistently selectable or
   announced.** Mark diagnostic text selectable, use accessibility live-region
   equivalents, and do not communicate recording/upload state by color alone.
10. **Low — `REC`, `UP`, and `WAKE` are implementation-oriented abbreviations.**
    Prefer Recording, Uploading, and Awake/Ready in accessible labels; visual
    abbreviations may remain only where space is constrained.

## Design system requirements

### Layout states

| State | Suggested range | Behavior |
| --- | --- | --- |
| Wide | >= 1600 px and sufficient height | Expanded project pane; inspector can remain expanded; resizable center-safe panes. |
| Laptop | 1100-1599 px | Compact project rail by default; one expanded side pane at a time; center stays dominant. |
| Constrained desktop | 760-1099 px | Project and inspector become overlay drawers; top navigation may use shorter labels. |
| Below desktop support | < 760 px | Show a deliberate unsupported/control-light layout unless a dedicated responsive design is implemented. |

Height matters as much as width. At 768 px, inspector sections should not all
open by default and primary actions must remain sticky without obscuring form
content.

### Tokens and components

- Type: page title, section title, body, label, caption, numeric status.
- Spacing: 4, 8, 12, 16, 24, and 32 px scale.
- Controls: 32 px dense, 36 px standard desktop, 44 px primary/touch/mobile.
- Color: neutral surfaces plus semantic success, warning, danger, info, and
  selected tokens with verified contrast.
- Shared components: `PageToolbar`, `Inspector`, `DisclosureSection`,
  `StatusBadge`, `SystemBanner`, `EmptyState`, `ErrorState`, `ActivityCenter`,
  `SelectionToolbar`, and `OverflowMenu`.
- Motion: 150-220 ms pane transitions; respect reduced-motion preferences; do
  not delay state changes or couple data loading to animations.

## Accessibility requirements

- Meet WCAG 2.2 AA for the operator web application.
- Keep every pointer target at least 24 x 24 CSS pixels or provide compliant
  spacing; use 44 x 44 for primary actions and all phone controls.
- Provide a visible focus indicator with sufficient contrast and do not allow
  sticky bars or overlays to obscure focus.
- Preserve logical focus order across left pane, top navigation, center
  workspace, and inspector. Collapsing a pane returns focus to its toggle.
- Give icon-only controls an accessible name and visible tooltip.
- Use real headings, regions, lists/trees, dialogs, tabs, and switches matching
  behavior. Do not use a toggle-looking button without `aria-pressed` or switch
  semantics.
- Announce recording start/stop, upload completion/failure, analysis task
  creation, and blocking errors without repeatedly announcing live metrics.
- Support keyboard-only selection, range selection, modal dismissal, disclosure
  controls, and overflow menus.
- Test at 200% zoom and with Windows text scaling; center content must reflow
  rather than become horizontally inaccessible.
- Never depend on red/green/purple alone. Pair semantic color with icon, label,
  and shape.

## Runtime failures versus UX defects

Some captured errors are environmental or routing failures, not proof of lost
data:

- `File unavailable` can be a preview-routing failure; see
  `agents_docs/troubleshooting/recording_playback.md`.
- `Failed to fetch` may originate from EdgeRelay, storage agent, PC backend,
  model service, or a browser request.
- Empty camera cards can be correct when no phone is connected.
- Host storage can legitimately be unavailable while Docker-volume storage
  remains usable.

The UX defect is that these different conditions are presented with generic or
contradictory copy. The redesign must not hide operational truth. It must name
the failing capability, preserve the last valid state when safe, distinguish
degraded from blocked operation, and provide the correct recovery path.

## Product-level acceptance outcomes

The redesign is successful when:

1. A new operator can create/select a session, pair cameras, confirm readiness,
   and start recording without opening infrastructure settings.
2. An experienced operator can reach advanced controls within two interactions
   without keeping them permanently visible.
3. Pane changes never alter loaded domain data or selection.
4. Every workflow shows its current stage, first blocker, and next valid action.
5. At 1366 x 768 the center task remains dominant and primary actions remain
   visible.
6. The phone's local recordings and diagnostics are reachable through explicit
   navigation.
7. Errors identify the affected service/capability, preserved functionality,
   and a recovery action.
8. Keyboard, screen-reader, zoom, and target-size validation passes the matrix
   in the implementation roadmap.
