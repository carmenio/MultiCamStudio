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

## Phase status

| Phase | Workflow | Status | Evidence |
| --- | --- | --- | --- |
| 0 | Contracts, deterministic tests, benchmarks | In progress | [Phase 0](refactor_phases/phase_00_baseline.md) |
| 1 | Recordings and sessions | In progress | [Phase 1](refactor_phases/phase_01_recording_sessions.md) |
| 2 | Capture, EdgeRelay, signaling, phones | Pending | Not started |
| 3 | Calibration | Pending | Not started |
| 4 | Point detection and post-processing | Pending | Not started |
| 5 | Triangulation and 3D | Pending | Not started |
| 6 | Pipeline, exports, and settings | Pending | Not started |
| 7 | Cross-cutting cleanup and final hardening | Pending | Not started |

## Universal acceptance gate

Each completed phase requires green affected tests and builds, live workflow
validation, before/after benchmarks on the same environment, median and p95 no
more than 3% slower, updated Markdown evidence, and a no-migration rollback path.

