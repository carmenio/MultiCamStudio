# UI/UX audit implementation

Status: implemented in the laptop operator web and Expo camera companion  
Design source: `agents_docs/design/ui_ux_audit.md`  
Delivery source: `agents_docs/implementation/ui_ux_roadmap.md`

## Architecture delivered

- `SessionResourceProvider` is the only owner of the operator's canonical session collection and selected session. Pipeline overview data is enrichment and cannot replace canonical rows.
- Operator loading, stale, partial, empty, and error presentation uses shared resource and operation-error models. Errors retain technical detail while naming the affected capability and recovery action.
- The desktop shell has wide, laptop, constrained, and unsupported modes with mode-scoped pane preferences. Visible workflow labels changed without changing internal page keys.
- Sessions navigation, Settings, and Activity are shell concerns. Settings reuses the existing storage, cache, model, and connectivity APIs; Activity reuses task and upload contexts.
- High-frequency workflow commands live beside their content. Inspectors progressively disclose properties and advanced controls.
- Expo Router now owns phone navigation while one long-lived `PhoneRuntimeProvider` keeps signaling, capture, finalization, recording storage, and upload recovery mounted across route changes.

## Compatibility boundaries

- Backend endpoints, payloads, session and recording-set identifiers, same-origin edge routing, and task creation are unchanged.
- Ordered card selection and local-only pending-footage deletion remain unchanged.
- Recording playback retains bounded per-camera retry and does not discard unaffected cameras.
- Phone Record/Stop remains laptop-controlled. Native finalization queues, relative durable locators, upload checkpoints, retry, and delete guards are unchanged.
- Expo Router dependency changes require rebuilt iOS and Android development clients before device acceptance.

## UI ownership

- Header: workflow destinations, Settings, Activity, and Export only.
- Sessions pane: session hierarchy and selection.
- Workspace toolbar: the primary action for the current task or selected object.
- Inspector: contextual properties and advanced disclosure.
- Settings: storage/cache, camera defaults, models, connectivity, export presets, and troubleshooting.
- Activity: background tasks, transfers, failures, completion, and cancellation.

### Pipeline disclosure

- The Pipeline toolbar owns the indeterminate-capable **Select all** control and the conditional **Run pipeline** action. Selection-mode and expand/collapse-all actions are intentionally absent; each session keeps its own disclosure chevron.
- Session and recording-set checkboxes remain mounted for stable selection semantics. Pointer devices reveal unselected controls on row hover or keyboard focus, selected controls remain visible, and non-hover devices show all controls.
- Each recording set always shows its highest/current stage. The complete Recorded through 3D track is progressive detail revealed on row hover or focus, and its hidden state consumes no workspace width.

### Global settings parity

- Storage and cache is shell-owned Settings functionality. It supports Docker roots and subfolders, host-agent folder browsing, the active path, capacity and availability state, guarded apply, refresh, and error recovery.
- **Refresh storage index** asks EdgeRelay to rescan storage metadata. **Clear browser video cache** removes the current operator browser's playback cache after confirmation. These operations have separate APIs, busy states, and feedback and must not be combined under a generic cache action.
- Capture no longer duplicates Laptop Storage. Recordings, Calibration, and Detection no longer duplicate browser-cache maintenance. Capture quality/defaults and analysis-specific view, model, run, and 3D controls remain contextual inspector concerns.

## Known validation boundary

Automated web, TypeScript, service, and bundle checks run on Windows. Safe-area layout, Dynamic Type, Android font scaling, certificate repair, background/foreground transitions, and native recording/finalization/upload behavior still require rebuilt installed development clients on physical iOS and Android devices.
