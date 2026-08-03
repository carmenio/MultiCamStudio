# Phase 0: Baseline, Contracts, and Benchmark Infrastructure

## Original problem

The repository had broad behavior coverage but no uniform performance harness.
Several suites also produced environment or assertion noise that prevented them
from acting as reliable refactor gates.

The untouched baseline was:

| Area | Result | Classification |
| --- | --- | --- |
| Backend | 518 total; 343 pass, 174 errors, 1 failure | Errors were eager full-app Supabase construction; failure was stale `size_bytes` expectation |
| Operator web | 657 total; 654 pass, 3 fail | Two stale timing-source assertions and one visualization SVG exemption |
| Signaling | 3 pass; smoke file failed to load | Declared `ws` dependency was not installed locally |
| EdgeRelay | 43 pass | Green |
| Camera mobile | 53 pass; type-check and native-patch validation pass | Green |

## Changes

- Recordings route tests now mount the real controller on a controller-local Flask
  app. Unrelated controller constructors no longer require live Supabase credentials.
- Three direct sync tests now isolate the calibration database adapter as well.
- The stale EdgeSync assertion includes the already-observable `size_bytes` update.
- Detections timing assertions now identify model-FPS fallback when video timing is
  absent; the DOM case that genuinely uses video timing remains unchanged.
- Triangulation controller tests mount the real controller on a controller-local
  Flask app. Focused mixed suites no longer depend on earlier tests leaving mocked
  full-application imports in `sys.modules`.
- The design-system contract exempts the export point visualization from the ban on
  inline action SVGs. Interactive chrome remains library-backed.
- `npm ci` restores the signaling test environment; no tracked signaling source or
  dependency declaration changed.

## Verification

- Recordings controller: 91 passed.
- Application worker boot: 6 passed.
- Detections timing and design-system focus: 31 passed.
- EdgeSync stale assertion focus: 1 passed.
- Signaling: 10 passed, 1 skipped because FFmpeg is unavailable.
- Full backend: 519 passed.
- Full operator web: 657 passed; production build passed.
- EdgeRelay: 43 passed.
- Camera mobile: 53 passed; type-check and native-patch validation passed.

After the latest characterization additions, the complete backend suite passes
588 tests. This includes the 21-test capture lifecycle suite and eight focused
media-route cases added after the prior complete run. The complete operator suite
passes with the repository's bounded-worker
command and includes 7 new RecordingPage contract tests (664 total); its
production build also passes. The expanded EdgeRelay suite passes 48 tests.
Existing React `act(...)`, duplicate-key,
missing-Expo-base-config, and large-chunk warnings remain baseline noise.

One high-severity npm advisory is present in the signaling dependency tree. It is
not changed in this refactor because an upgrade requires a separate compatibility
and security review.

## Characterization coverage and gaps

The following matrix is the traceability baseline for extraction work. A green
automated suite does not close a listed live, performance, browser, or physical
device gap.

| Contract family | Current characterization evidence | Gap that must be closed before the owning extraction is accepted |
| --- | --- | --- |
| Sessions | `test_sessions_controller.py`; operator session persistence and SessionResourceContext suites | Add a live session/overview latency pair and retain exact full-versus-UI profile response identities. |
| Cameras and pairing | `test_session_cameras_controller.py`; Filming camera/page suites; camera-mobile config, signaling, selection, and pairing-presentation suites | Physical iOS/Android pairing, reconnect, certificate, and transport-mismatch recovery are unavailable in this phase. |
| Recording media and playback source | Recording controller tests cover original, synchronized, and preview media headers; byte ranges and exact `206`/`Content-Range` behavior; exact missing-file responses; adaptive headers, traversal rejection, file-scheme fallback, original/synced selection, preview precedence, HLS-ready/warmup paths, missing local media, and the `200` warning fallback after database or adaptive-preparation failures. Playback hooks, cache, timeline, and viewer suites cover browser orchestration. A real three-camera browser run captures cold preview startup, first decoded frame, and synchronized playback start. | Multi-camera seek readiness currently times out after 20 seconds and is retained as unavailable; cutting remains unmeasured. |
| Playback-session lifecycle | Ten focused route tests cover create validation, all-row and filtered selection, database ordering, distinct empty-result errors, signaling precedence/fallback, five offset aliases, direct/probed/zero duration, join tokens, stats, and repeated delete | The extraction is an early Phase 1 slice, not Phase 0 completion. Cold-cache and browser-consumer evidence remain unavailable. |
| Resumable and multipart uploads | Recording controller tests cover required fields, sorted resume state, chunk index behavior, checksum conflict/mismatch, incomplete and missing chunks, partial-output retention, repeated completion/collision suffixes, post-assembly persistence failure, task enqueueing, imported signaling files, and finalize partial/all-failure behavior. A deterministic production-route baseline now captures server initialization/resume plus 16 MiB chunk-write and assembly/checksum throughput with exact output identity. | Physical Stop-to-upload-init and interrupted-network recovery remain unavailable; current permissive out-of-range index and repeated-completion behavior are frozen until separately changed. |
| Capture sessions | Twenty-one focused tests cover start/create/reuse, no-active and stale-active behavior, owner-protected status/PATCH/stop/abort, unknown state and invalid snapshot normalization, repeatable abort, idempotent finalize, no-success and all-import-failed completion, empty-set cleanup, shared ingest, partial import, invalid session identity, and unexpected finalize errors | Add a true concurrent-finalize race test plus physical Stop-to-upload-init and interrupted-network validation. |
| EdgeRelay, host storage, and Edge-to-PC sync | The 48-test `test_edge_relay.py` suite covers caching, storage selection, host-agent transfer, resumable and legacy upload, deletion guards, capture start/finalize recovery, invalid pairing resolution, stop/status/abort shapes, selected transfer start plus pause/retry transitions, and generic/viewer proxy preservation. It freezes the current compatibility behavior where stop/abort of an unknown capture return `200` and those routes do not reject a different supplied owner. The 17-test `test_edge_recording_repair.py` suite additionally freezes PC bearer authorization, capture and recording initialization, duplicate/conflicting chunks, chunk validation, capture finalize/status shapes, completion, repair, and preview enqueueing. | Add live host-folder transfer/recovery evidence. |
| Signaling and legacy browser phone | Signaling smoke/config suites cover upload/download, extension/transcode rules, room isolation, viewer rejoin, and legacy control mapping; browser-phone source contract tests cover IndexedDB and active compatibility markers | FFmpeg transcode evidence is skipped when FFmpeg is unavailable. No physical browser-phone recording/upload recovery run is recorded for this phase. |
| Calibration | Controller, database, generator, service, viewer, and viewer-renderer suites; Calibration page/component/flow suites | Add controlled preflight, fixed-fixture batch processing, status, and viewer-generation baselines plus a live rendered-viewer equivalence capture. |
| Point detection and post-processing | Controller, catalog database, result persistence, service, post-processing pipeline, segmenter, API, scheduler, hydration, page, sidebar, and toolbar suites. Live summary and first/seeked/sequential window retrieval are captured. A deterministic three-camera, 60-second production-code baseline now covers all six ordered post-processing stages and 36 five-second segment outputs with full canonical equivalence hashes. | Live overlay equivalence remains absent; post-processing persistence/task dispatch is not included in the pure processing timing. |
| Triangulation and 3D | Controller, service, database, API, page, viewer, and training-timeline suites cover mapping, variant resolution, diagnostics, audit, runs, results, assignments, and training transitions. A deterministic production-service baseline triangulates 81,000 observations into 27,000 accepted points with fixed full-result and calibration-fixture identities. | Add result-not-found and remaining training/reference-media error shapes plus browser camera-transform/render equivalence, first usable render, playback-start, and seek baselines. |
| Dataset exports | The 17-test controller suite plus planner, coordinator, writer, history, service, and ExportWizard suites cover reviewed specifications, explicit sources, mappings, missing sources, history, and synchronous compatibility. Exact route contracts now include validation and unexpected preflight errors, missing task service, stale reviews, zero eligible sets, and numeric/opaque missing-job lookups. A production preflight baseline captures an eligible fixed-source plan with stable semantic and review hashes. A separate fixed three-camera `two_d_3d` baseline exercises production artifact writing, checksums, manifest integrity, and atomic finalization across five measured exports with stable output identity. | Live server-side export task dispatch and history polling remain uncaptured; writer/finalization throughput is now frozen. |
| All-tab pipeline and task queue | Twenty-five focused route tests now freeze task list/detail filtering and shaping, queued cancellation, running cancel requests, completed cleanup, persistent-store fallback, five-stage order, exact task payloads, dependency chaining, duplicate-sync reuse, sync-disabled skipping, per-set calibration linking, validation errors, adapter unavailability, and partial task-creation failure. Four fallback-store tests additionally freeze blocked dependencies, missing-parent cancellation, recursive cancellation, and running-task cancel requests. Overview service and worker/task-normalization suites retain stage precedence and dispatch behavior. | Add persistent TaskDatabase dependency parity and live orchestration timing. Current validation-before-stage-selection and nontransactional partial effects are documented baseline defects. |

Seven focused RecordingPage contract tests additionally freeze visible-order
export projection, clearing on session removal, partial-deletion retention, exact
cut submission and terminal task behavior, manual-sync downstream invariants,
and prefetch cleanup across set changes and unmounting.

## Verified fixture identities and evidence limits

| Fixture or environment | Verified identity | Permitted use |
| --- | --- | --- |
| Live PC playback slice | Session 49; recording set 177; recordings 646, 647, and 648; three cameras; durations 48.4833, 44.1833, and 53.6833 seconds; sizes 111,199,373, 102,355,070, and 122,456,971 bytes | Warm playback-session before/after evidence only. It must not be generalized to cold playback, media startup, seek, sync, cut, or another workflow. |
| PC runtime | Windows build 10.0.26200, Intel Core i9-11900K, 68,595,343,360 bytes RAM, Balanced power mode; Docker-published backend at `https://localhost:5000`; database snapshot observed 2026-08-03 | Reuse only when candidate metadata confirms the same controlled environment and fixture identity. |
| Automated backend/web/edge/mobile fixtures | Test-local temporary files, in-memory or mocked adapters, and deterministic response rows owned by the named suites | Contract characterization only; test duration is not application-performance evidence. |

Controlled read-only live baselines now cover service-cold, header-bypassed, and
warm session UI retrieval, playback-source
resolution, one-byte media transport readiness, calibration viewer and batch
status, detection summary plus first/seeked/sequential five-second segments,
deterministic post-processing and segment generation,
triangulation metadata/status, retrieval of a 35,815,719-byte triangulation
result, and fixed-fixture production triangulation. Browser evidence covers
three-camera preview startup, first decoded frame,
and synchronized playback start. They do not cover database/operating-system cold
state, successful multi-camera seeking, cutting, pairing/control, physical upload,
live export task dispatch, or full-pipeline dispatch. Deterministic PC upload
route/filesystem behavior and production export writing/finalization are captured
independently of the live database and configured export root. No Phase 0 physical
iPhone or Android run is recorded for pairing, preview, maximum-profile recording,
asynchronous finalization, upload recovery, background/foreground behavior,
Dynamic Type, or Android font scaling. A previously rebuilt client or older UI
acceptance note is not a substitute for phase-scoped device evidence.

`pc/API.md` also remains incomplete relative to registered controller routes. The
master migration inventory records the concrete route families; route-level
characterization remains the acceptance source until the API document is updated
in its owning documentation task.

## Rollback

Revert the test-fixture and expectation commits. No runtime code, schema, stored
data, or deployment configuration is changed by these baseline repairs.

## Remaining work

- Capture the required untouched live workflow baselines. This phase is **not
  complete**, and no later structural phase may be accepted until that evidence
  is committed.
- The playback-session extraction was discovered during independent review to
  have started early. It remains an unaccepted Phase 1 slice; its evidence does
  not substitute for the Phase 0 workflow matrix.
