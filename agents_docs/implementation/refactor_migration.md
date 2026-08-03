# MultiCamStudio Refactor Migration

## Purpose

This migration improves readability, responsibility ownership, naming, and
testability without changing observable behavior. Work is delivered as vertical
workflow phases. Each phase must preserve HTTP, persistence, task, storage,
client-state, deployment, compatibility, and performance contracts.

## Module design rules

- Controllers and UI pages translate external input and compose workflow modules.
- A workflow module exposes a small interface and owns the complex behavior behind it.
- External dependencies are accepted at real seams. Production and test adapters
  justify the seam; speculative pass-through interfaces are not added.
- Characterization tests exercise public routes or user-visible interfaces and must
  remain stable when implementations move.
- Mechanical moves, behavior extraction, duplicate deletion, and documentation are
  separate commits.
- Runtime defects discovered during the migration are recorded separately instead
  of being silently mixed into a refactor.

## Frozen contract inventory

The source controllers and deployed clients are authoritative where `pc/API.md`
has drifted. The contract inventory includes:

- Sessions, cameras, pairing, recording configuration, and device discovery.
- Recording media, resumable upload, capture lifecycle, playback sessions, sync,
  cuts, deletion, calibration links, and Edge-to-PC synchronization.
- Calibration batches, status, and database-rendered viewers.
- Point-detection catalog, run, variant, checkpoint, diagnostics, skeleton
  references, and immutable five-second playback segments.
- Triangulation runs, results, audits, training segments, skeleton definitions, and
  recording-set assignments.
- Dataset export, task queue, and All-tab orchestration routes.
- EdgeRelay storage, upload, transfer, capture, cache, pairing, proxy, and legacy
  browser-phone routes.
- Signaling messages and legacy-to-canonical control mappings.

Registered task types remain:

`sync_recording_set`, `recording_upload`, `build_recording_preview`,
`cut_recording_set`, `calibration_batch`, `point_detection_run`,
`point_detection_smoothing`, `point_detection_shift`,
`point_detection_postprocess`, `triangulation_run`, and `export_dataset`.

Persisted browser, IndexedDB, session-storage, and native AsyncStorage keys are
part of the interface and may not be renamed during this migration.

### Concrete HTTP and transport families

This table is a route-family index rather than a replacement for request and
response characterization. Route decorators in the controllers and deployed
EdgeRelay are the source of truth; several entries are newer than `pc/API.md`.

| Family | Frozen routes and compatibility forms |
| --- | --- |
| Sessions | `GET /api/sessions-info`; `POST /api/add-session` and `POST /api/sessions`; `GET`, `PATCH`, and `DELETE /api/sessions/<session_id>` |
| Cameras and pairing | `GET`, `POST`, and `DELETE /api/session-cameras`; `POST /api/session-cameras/copy`; `POST /api/pair/start` and `/api/session-cameras/pairing-token`; `POST /api/pair/complete` and `/api/session-cameras/pairing-resolve`; `GET /api/session-cameras/recording-config`; `GET /api/devices` |
| Recording media and adaptive playback | `GET /recordings/<path>`, `/synced-recordings/<path>`, `/preview-recordings/<path>`, and `/adaptive-streams/<recording_id>/<fingerprint>/<path>`; `GET /api/recordings/<recording_id>/playback-source` |
| Playback sessions | `POST /api/playback/sessions`; `POST /api/playback/sessions/<session_id>/join`; `GET /api/playback/sessions/<session_id>/stats`; `DELETE /api/playback/sessions/<session_id>` |
| Upload and capture | `POST /upload/init`; `PUT /upload/<upload_id>/chunk`; `POST /upload/<upload_id>/complete`; capture-session `start`, `active`, `PATCH`, `status`, `stop`, `finalize`, and `abort`; recording `upload`, `upload/batch`, `upload/task`, and `finalize` |
| Recording-set lifecycle | `DELETE /api/recordings`; `DELETE /api/recording-sets`; recording-set `sync`, `sync/status`, `cuts`, `manual-sync/context`, `manual-sync/update`, and `calibration-link` |
| Edge-to-PC recording sync | Capture `init`, recording `init`, `chunk`, and `complete`, then capture `finalize` and `status` under `/api/edge-sync` |
| Calibration | `POST /api/calibrations/batches`; batch `status`; `GET /api/calibrations/<calibration_id>/viewer`; `GET /calibration-viewers/<calibration_id>.html` |
| Point detection | Model/group CRUD and endpoint probe; recording-set `run`, `smoothing/run`, `postprocess/settings`, `postprocess/run`, `latest`, `latest-metadata`, `segments`, `prediction-chunks`, and `summary`; session `statuses`, `summaries`, and `overlay-summaries` |
| Skeleton references | Definition reference `GET` and `POST`; reference-media `GET content`, `PATCH`, and `DELETE`. These routes are currently registered by `PointDetectionsController` even though their paths begin `/api/3d`. |
| Triangulation and 3D | Skeleton-definition CRUD; recording-set skeleton assignment; session statuses; triangulation `run`, `runs`, `runs-lite`, `latest`, result, and audit; training-segment list, start, end, and delete |
| Exports, tasks, and pipeline | Export settings, preflight, jobs, job detail, point-order presets, and synchronous `session-packages`; task list, detail, cancel, cancel-request, and completed-task deletion; All-tab overview and run |
| EdgeRelay and storage | EdgeRelay mirrors sessions, cameras, pairing, capture, upload, storage, transfer, recording-cache deletion, `/api/<path>` proxying, and calibration-viewer forwarding. The host storage agent freezes storage status/root/list plus chunk, complete, metadata, file, and delete routes. |

The signaling interface accepts room `join`, WebRTC `offer`, `answer`, `ice`, and
`viewer-ready` messages and relays unknown room messages unchanged. Messages
default to `protocolVersion: 2`. The legacy `control` actions remain mapped as
follows:

| Legacy action | Canonical type |
| --- | --- |
| `start-recording` | `recording.start` |
| `stop-recording` | `recording.stop` |
| `update-settings` | `device.configure` |
| `request-device-info` | `device.hello` |
| `request-recording-state` | `recording.progress` |

The signaling HTTP compatibility interface also retains `POST /upload`,
`POST /upload/blob`, and `GET /recordings/<filename>`.

### Concrete persisted-client inventory

| Store | Frozen identifiers |
| --- | --- |
| Operator local storage | `multicam:selectedSessionId`, `multicam:rightSidebarCollapsed`, `multicam:shell:<mode>:<pane>Collapsed`, `multicam:operator-id`, `multicam:active-capture-session:v1`, `multicam:recordingDisableVideoCaching`, and `multicam:point-detection:set-statuses:v1` |
| Workflow preferences | `triangulation.min_confidence:<recording_set_id>`, `three_d.view_settings:<recording_set_id>`, and `multicam:right-sidebar:v1` keys for Filming, Calibration, Detections overview/set, and 3D set state |
| Operator session storage | `multicam.export-wizard.draft.v1` |
| Operator IndexedDB | `multicam-recording-playback-meta` version 2 and `multicam-thumbnails` version 2 |
| Expo AsyncStorage | `multicam.cameraMobile.serverConfig.v1`, `multicam:local-recordings:v1`, and `multicam:upload-queue:v1` |
| Browser-phone persistence | Local storage `multicam:browser-upload-target:v1`; IndexedDB `multicam-recordings` version 3 with `recordings`, `recordingChunks`, and `uploadQueue` stores |

Task-type matching remains trimmed and case-normalized internally, but the
canonical persisted values listed above remain stable. Storage layout contracts
include original, incoming chunk, synchronized, preview, adaptive-stream cache,
EdgeRelay recording, host-agent recording, and server-side dataset-export roots;
the migration may move ownership code without moving those files or changing
their public locators.

## Phase status

| Phase | Workflow | Status | Evidence |
| --- | --- | --- | --- |
| 0 | Contracts, deterministic tests, benchmarks | In progress | [Phase 0](refactor_phases/phase_00_baseline.md) |
| 1 | Recordings and sessions | Paused at Phase 0 gate | [Phase 1](refactor_phases/phase_01_recording_sessions.md) |
| 2 | Capture, EdgeRelay, signaling, phones | Pending | [Phase 2](refactor_phases/phase_02_capture_edge_phone.md) |
| 3 | Calibration | Pending | [Phase 3](refactor_phases/phase_03_calibration.md) |
| 4 | Point detection and post-processing | Pending | [Phase 4](refactor_phases/phase_04_point_detection.md) |
| 5 | Triangulation and 3D | Pending | [Phase 5](refactor_phases/phase_05_triangulation_3d.md) |
| 6 | Pipeline, exports, and settings | Pending | [Phase 6](refactor_phases/phase_06_pipeline_exports_settings.md) |
| 7 | Cross-cutting cleanup and final hardening | Pending | [Phase 7](refactor_phases/phase_07_final_hardening.md) |

## Universal acceptance gate

Each completed phase requires green affected tests and builds, live workflow
validation, before/after benchmarks on the same environment, median and p95 no
more than 3% slower, updated Markdown evidence, and a no-migration rollback path.
