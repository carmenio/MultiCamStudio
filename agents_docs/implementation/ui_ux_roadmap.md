# UI/UX Implementation Roadmap

Status: decision-complete roadmap  
Design source: `agents_docs/design/ui_ux_audit.md`

## Objective

Turn the audit into a sequence of safe, reviewable changes without breaking
recording, synchronization, storage, upload, analysis, export, routing, or
native finalization contracts. Each phase must leave the application usable and
must validate degraded states as well as the happy path.

## Non-negotiable boundaries

- UI work may reorganize presentation and local UI state but must not silently
  change API payloads, route derivation, recording ownership, upload lifecycle,
  task creation, or session/recording-set identifiers.
- The operator web app remains same-origin in edge mode.
- The phone continues to derive API, signaling, upload, and certificate URLs
  from the operator-provided runtime origin.
- iOS recording stop/finalization remains asynchronous and bounded on its
  dedicated queue. Local recording locators remain relative and durable.
- Pending-footage deletion remains local to the device and recording UUID.
- Native phone changes require a rebuilt development client; TypeScript-only UI
  changes still require on-device validation against the installed native
  modules.
- Existing Explorer-style ordered selection remains the shared card-selection
  contract.

## Phase 0 — Stabilize UX state

Goal: remove contradictions and generic failure handling before visual
restructuring.

### P0.1 Preserve sessions through pane transitions

- Reproduce UX-001 with deterministic tests around `App.tsx`, sidebar visual
  transitions, and All/Pipeline data props.
- Separate sidebar animation state from sessions, current selection, and All
  page filters.
- Preserve the last valid session payload during refresh; show refresh state or
  a non-destructive warning instead of replacing content with an empty state.
- Verify repeated collapse/expand, width changes, active-page changes, and
  local-storage restoration.

Acceptance:

- Loaded session and recording-set counts never change from a visual pane
  transition.
- The selected session and recording set remain stable unless the backing data
  proves they no longer exist.
- A refresh failure keeps cached/previous content and marks it stale.

### P0.2 Introduce explicit async states

- Add shared loading, empty, partial/offline, and error-state primitives.
- Replace raw `Failed to fetch` strings with structured presentation containing
  capability, consequence, retry, and optional troubleshooting details.
- Map session, storage, transfer, playback, model, calibration, triangulation,
  and export errors to user-facing copy without discarding the original detail
  from logs/diagnostics.
- Keep the existing playback retry hook and routing checks; change only how
  recovery is presented.

Acceptance:

- Every data-fetching screen has fixtures/tests for loading, empty, retained
  stale data, partial data, recoverable failure, and blocking failure.
- A generic network exception never appears alone in visible UI.
- Playback failure on one camera does not replace otherwise usable recordings.

### P0.3 Establish a state vocabulary

- Define shared status names for queued, running, completed, failed, stale,
  recording, finalizing, uploading, ready, offline, and blocked.
- Document which states are domain states versus display-only derived states.
- Create one status badge/banner mapping used by task, transfer, recording, and
  analysis surfaces.

Acceptance:

- The same underlying state has the same visible label, semantic color, icon,
  and accessible description in every workflow.

## Phase 1 — Rebuild the shared desktop shell

Goal: establish clear ownership and responsive behavior before individual page
redesigns.

### P1.1 Design tokens and shared primitives

- Extract color, type, spacing, radius, focus, control-size, pane-width, and
  motion tokens from the monolithic application stylesheet.
- Add shared button variants, tooltips, icon buttons, segmented controls,
  switches, disclosure sections, page toolbars, inspectors, selection toolbars,
  overflow menus, and activity indicators.
- Keep existing visual styling functional while migrating page-by-page; do not
  require a single high-risk stylesheet rewrite.

Acceptance:

- New components have isolated tests for accessible names, keyboard behavior,
  pressed/expanded state, disabled state, and focus restoration.
- Tokens can express wide, laptop, and overlay shell states without page-local
  width overrides.

### P1.2 Project navigation

- Rename the pane to `Sessions` or display the active project name.
- Keep search and new-session controls in expanded mode.
- Replace the zero-state task footer with an activity icon/badge and flyout.
- Improve compact session identification using a stable short token plus status
  marker, selected state, tooltip, and an optional temporary flyout list.
- Preserve tree expansion and ordered selection behavior.

Acceptance:

- A collapsed-rail user can identify the active session and switch sessions
  without permanently expanding the pane.
- All icon-only controls have tooltips and accessible names.

### P1.3 Workflow navigation and command bars

- Rename stages according to the audit: Pipeline, Capture, Recordings,
  Calibration, Detection, and 3D.
- Anchor navigation to the center workspace and use shorter visible labels only
  at the constrained breakpoint; accessible names remain complete.
- Move Export into the owning workspace command bar while keeping it globally
  reachable where required.
- Add one consistent page toolbar layout: identity on the left, primary and
  secondary actions on the right, overflow last.

Acceptance:

- Current stage is visually and programmatically identifiable.
- Top navigation contains destinations only, not content actions.
- Navigation order and selection remain stable across pane states.

### P1.4 Responsive pane manager

- Implement `wide`, `laptop`, and `overlay` shell modes using width and height.
- Wide: expanded project pane and optional expanded inspector.
- Laptop: compact project rail by default and only one expanded secondary pane.
- Overlay: panes open above the center content, trap neither page focus nor
  scroll, and close predictably.
- Persist user preference per shell mode without applying an incompatible wide
  preference to a constrained viewport.

Acceptance:

- Validate at 1920 x 1080, 1600 x 900, 1366 x 768, 1100 x 700, and 1024 x 768.
- At 1366 x 768 the center retains at least 60% width with one pane open.
- Primary actions and current-state summaries remain visible without horizontal
  page scrolling.

## Phase 2 — Simplify operator workflows

Goal: move task controls next to task content and remove unrelated inspector
content.

### P2.1 Capture and camera management

- Add a capture toolbar with Record/Stop, duration, armed camera count, storage
  readiness, and a single blocker summary.
- Reduce the inspector to selected-camera/current-capture properties.
- Move storage configuration to a dialog under Settings; leave readiness, free
  space, and destination summary in Capture.
- Move Copy Cameras to session/camera management.
- Make quality presets the routine path and move raw encoding/shutter details to
  Advanced.
- Convert laptop footage into an activity tray that expands when work exists or
  fails.
- Hide unavailable metrics until a camera signal supplies them.

Acceptance:

- A ready operator can begin capture without scrolling an inspector.
- A blocked recording names every blocker before Record is enabled.
- Changing storage or quality still calls the existing APIs with the existing
  payloads.

### P2.2 Recordings and synchronization

- Replace blank cards with thumbnails when available and compact metadata when
  unavailable.
- Put Add videos, Sync, playback recovery, and set-level overflow in the open
  recording-set toolbar.
- Show manual sync properties only while manual mode is active.
- Move cache maintenance to overflow/Settings with scope confirmation.
- Combine per-camera media errors into a recording-level recovery summary while
  retaining individual retry controls.

Acceptance:

- Users can distinguish loading, unavailable, and genuinely empty recordings.
- Synced/not-synced state and the next valid action are visible on every card.
- Existing focused playback and synchronization tests continue to pass.

### P2.3 Calibration and detection

- Add collection toolbars for filter, sort, view, selection count, and batch
  actions.
- Put blocker and next action on every card.
- Move video/camera view selection out of inspectors.
- Make uncalibrated/unsynced inclusion explicit filters with warning semantics.
- Move model installation/service administration to Settings; keep model preset
  selection in Detection.

Acceptance:

- Each card states prerequisite, current stage, and next valid action.
- A service failure preserves loaded cards and identifies the failed capability.
- Batch actions use the existing ordered-selection contract.

### P2.4 Pipeline overview

- Replace repeated status rows with a stage progression for each recording set.
- Show the first blocker and next available stage.
- Reveal a labeled selection toolbar only after selection.
- Make Run name or summarize enabled stages before task creation.
- Collapse the empty queue into the shared activity center.

Acceptance:

- An operator can answer what is ready, blocked, running, and next without
  opening every stage.
- Queue/task creation still uses existing task APIs and identifiers.
- Pane transitions pass the Phase 0 state-preservation tests.

### P2.5 3D and export

- Default the 3D inspector to View plus the next required workflow action.
- Keep view presets visible and move raw camera coordinates to Advanced.
- Use semantic switches for persistent boolean properties.
- Separate training-segment mode from normal viewing/triangulation.
- Convert Export into a named wizard with Selection, Points, Mapping,
  Connections, and Review steps; preserve entered state when moving backward.

Acceptance:

- Before triangulation, prerequisites and Run 3D dominate the inspector.
- After results load, view controls become available without obscuring the
  viewer.
- Export validates in context and displays a final scope/path summary before
  creation.

## Phase 3 — Refactor the Expo companion

Goal: make the complete phone capability reachable through native, camera-first
navigation while preserving capture/upload contracts.

### P3.1 Split the monolithic app

- Introduce Expo Router with route components for pairing, camera, recordings,
  and settings/diagnostics.
- Move reusable view components, hooks, and presentation models out of the route
  directory.
- Keep signaling, capture pipeline, recording store, upload processor, and
  filesystem adapters as services with unchanged public contracts.
- Replace custom root-screen switching and unreachable renderer functions with
  explicit navigation.

Acceptance:

- Camera and Recordings are reachable top-level destinations after pairing.
- Back navigation never disconnects or stops recording unless the user confirms
  an explicit command.
- Existing service tests pass without payload or lifecycle changes.

### P3.2 Pairing onboarding

- Implement Scan -> Permissions -> Trust if required -> Connected progression.
- Use the QR-derived origin automatically.
- Hide manual protocol/host/port and raw probe information under Advanced
  troubleshooting.
- Show certificate download/install instructions only after a trust check fails
  and adapt wording by platform.
- Preserve automatic deep-link pairing and manual-value fallback.

Acceptance:

- The routine path requires one scan and only the permissions/trust actions the
  device actually needs.
- A failed step identifies the step, preserves the pairing value, and offers
  retry plus Advanced details.

### P3.3 Camera-first live experience

- Make preview fill the screen while respecting both safe areas.
- Keep connection, recording state/duration, storage/upload warning, camera
  switch, and essential manual controls visible.
- Move bitrate, requested/actual FPS detail, pipeline name, raw connection
  status, and diagnostics into a sheet.
- Use haptics and redundant visual/text confirmation for Record/Stop where
  platform support permits.

Acceptance:

- Record/Stop and camera switching have at least 44 x 44 targets.
- Recording/finalizing/uploading states remain visible through navigation and
  app foreground/background transitions.
- Native finalization deadlines and queue ownership remain unchanged.

### P3.4 Local recordings and diagnostics

- Connect the existing local-recording list, playback, retry/send, progress, and
  delete operations to the Recordings route.
- Keep delete local-only, block deletion during active upload, and retain the
  existing confirmation contract.
- Put session diagnostics and connection issue history in Settings/Diagnostics;
  make important technical text selectable.

Acceptance:

- Pending, uploading, ready, and failed recordings are distinguishable without
  color alone.
- Historical failure cannot replace the newest recording status.
- Recordings remain accessible after an app restart and locator changes are not
  introduced.

## Phase 4 — Accessibility and polish

Goal: complete WCAG 2.2 AA validation and remove residual inconsistency.

- Audit target size, spacing, contrast, focus visibility, focus order, headings,
  region names, dialogs, disclosure semantics, and live announcements.
- Add keyboard coverage for navigation, tree selection, cards, timelines,
  dialogs, menus, and pane toggles.
- Validate Windows 200% zoom and text scaling.
- Validate iOS Dynamic Type and Android font scaling on the rebuilt development
  clients.
- Normalize sentence case, terminology, empty-state copy, and action verbs.
- Add reduced-motion behavior and visual regression snapshots.

Acceptance:

- Automated accessibility checks have no serious or critical findings.
- Manual keyboard and screen-reader scripts pass.
- No essential desktop text is below 12 px; normal control text is at least
  14 px unless a documented dense-data exception exists.
- All phone controls and primary desktop actions meet 44 x 44; all remaining web
  targets meet WCAG 2.2 minimum size or spacing.

## Recommended implementation packages

These packages are intentionally independently reviewable:

1. All/Pipeline state-preservation regression tests and fix.
2. Shared async-state and error presentation.
3. Status vocabulary and semantic badge/banner components.
4. Design tokens and button/disclosure primitives.
5. Responsive shell and pane manager.
6. Project navigation and activity center.
7. Capture toolbar and inspector simplification.
8. Recording cards, viewer recovery, and sync ownership.
9. Calibration and detection collection toolbars.
10. Pipeline stage overview and batch toolbar.
11. 3D progressive inspector and export wizard.
12. Expo Router shell and pairing onboarding.
13. Expo camera and local recordings routes.
14. Cross-platform accessibility and visual regression pass.

Do not combine Phase 0 with visual shell work. State regressions must be fixed
and protected before component ownership changes make failures harder to
isolate.

## Validation matrix

| Surface | Scenario | Required validation |
| --- | --- | --- |
| Operator shell | 1920 x 1080, 1600 x 900, 1366 x 768, 1100 x 700, 1024 x 768 | Pane mode, center width, navigation, preserved selection/data, no hidden primary action |
| Operator shell | 200% zoom and Windows text scaling | Reflow, focus visibility, no clipped labels/actions |
| Sessions | Initial load, cached load, refresh, partial camera refresh, failure | Correct loading/stale/error state and preserved valid data |
| Capture | No cameras, connecting, partially live, all ready, recording, storage degraded | Blockers, Record/Stop ownership, retained usable cameras, activity tray |
| Recordings | Loading, empty, one media failure, all media failure, retry, unsynced, manual sync | Distinct state presentation and unaffected-camera playback |
| Calibration/Detection/3D | Missing prerequisite, ready, queued, running, failed, completed | First blocker, next action, shared task state, recovery |
| Export | Each wizard step, back/forward, invalid mapping, service failure, success | Preserved form state, focus, validation ownership, result summary |
| Phone pairing | QR success, permission denial, certificate trusted/untrusted, manual fallback | Progressive steps, retained input, platform repair copy |
| Phone live | Connect, switch camera, record, finalize, upload, disconnect, background/foreground | Stable status and unchanged native lifecycle |
| Phone recordings | Pending, uploading, failed, retry, ready, playback, delete | Durable locators, local-only deletion, active-upload guard |
| Accessibility | Keyboard, screen reader, reduced motion, contrast, target size | WCAG 2.2 AA and mobile target criteria |

## Required checks by change type

Operator web changes:

```powershell
npm --prefix laptop/apps/operator-web run test:run
npm --prefix laptop/apps/operator-web run build
```

Use focused suites first when baseline failures exist, and report unrelated
failures separately.

Phone TypeScript and service changes:

```powershell
Set-Location laptop/apps/camera-mobile
npx tsc --noEmit
npm test
```

Phone navigation or UI changes also require manual iOS and Android development-
client checks. Any native dependency/patch change requires a rebuilt client;
Metro reload alone is insufficient.

## Definition of done

A roadmap package is complete only when:

- Its audit IDs and acceptance criteria are referenced in the change.
- Happy, empty, loading, partial, offline, failure, and recovery states relevant
  to the package are tested.
- Keyboard and accessible-name behavior is tested for new controls.
- Wide and 1366 x 768 screenshots are reviewed for operator changes.
- Phone work is reviewed at approximately 375 x 812 and 430 x 932 on installed
  development clients.
- Existing public payloads and domain contracts remain unchanged or an explicit
  compatibility decision is documented.
- The knowledge graph is refreshed with `graphify update .` after code changes.

