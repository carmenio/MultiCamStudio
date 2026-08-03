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

After adding characterization coverage, the complete backend suite passes 537
tests. The complete operator suite passes with the repository's bounded-worker
command and includes 7 new RecordingPage contract tests (664 total); its
production build also passes. Existing React `act(...)`, duplicate-key,
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
| Recording media and playback source | Recording controller tests cover original and preview headers, adaptive headers, file-scheme fallback, original/synced selection, preview precedence, HLS-ready, and warmup paths; playback hooks, cache, timeline, and viewer suites cover browser orchestration | Add direct synchronized-media Range/CORS coverage, 206/Content-Range cases for all media roots, adaptive traversal/missing-file cases, playback-source missing/error fallbacks, browser first-frame, seek-readiness, and synchronized-playback benchmarks. |
| Playback-session lifecycle | Ten focused route tests cover create validation, all-row and filtered selection, database ordering, distinct empty-result errors, signaling precedence/fallback, five offset aliases, direct/probed/zero duration, join tokens, stats, and repeated delete | The extraction is an early Phase 1 slice, not Phase 0 completion. Cold-cache and browser-consumer evidence remain unavailable. |
| Resumable and multipart uploads | Recording controller tests cover required fields, sorted resume state, chunk index behavior, checksum conflict/mismatch, incomplete and missing chunks, partial-output retention, repeated completion/collision suffixes, post-assembly persistence failure, task enqueueing, imported signaling files, and finalize partial/all-failure behavior | Add controlled upload-throughput evidence and physical interrupted-network recovery; current permissive out-of-range index and repeated-completion behavior are frozen until separately changed. |
| Capture sessions | Twenty-one focused tests cover start/create/reuse, no-active and stale-active behavior, owner-protected status/PATCH/stop/abort, unknown state and invalid snapshot normalization, repeatable abort, idempotent finalize, no-success and all-import-failed completion, empty-set cleanup, shared ingest, partial import, invalid session identity, and unexpected finalize errors | Add a true concurrent-finalize race test plus physical Stop-to-upload-init and interrupted-network validation. |
| EdgeRelay, host storage, and Edge-to-PC sync | `test_edge_relay.py` covers caching, storage selection, host-agent transfer, resumable and legacy upload, deletion guards, capture start/finalize recovery, and viewer proxying; `test_edge_recording_repair.py` covers init/complete/repair and preview enqueueing | Add direct EdgeSync chunk/finalize/status contracts, EdgeRelay pairing-resolve, capture stop/status/abort, transfer pause/resume/retry transitions, proxy response preservation, and live host-folder transfer/recovery evidence. |
| Signaling and legacy browser phone | Signaling smoke/config suites cover upload/download, extension/transcode rules, room isolation, viewer rejoin, and legacy control mapping; browser-phone source contract tests cover IndexedDB and active compatibility markers | FFmpeg transcode evidence is skipped when FFmpeg is unavailable. No physical browser-phone recording/upload recovery run is recorded for this phase. |
| Calibration | Controller, database, generator, service, viewer, and viewer-renderer suites; Calibration page/component/flow suites | Add controlled preflight, fixed-fixture batch processing, status, and viewer-generation baselines plus a live rendered-viewer equivalence capture. |
| Point detection and post-processing | Controller, catalog database, result persistence, service, post-processing pipeline, segmenter, API, scheduler, hydration, page, sidebar, and toolbar suites | Add controlled summary, first-window, uncached-seek, sequential-window, segment-generation, and post-processing baselines. Live overlay equivalence is not Phase 0 evidence. |
| Triangulation and 3D | Controller, service, database, API, page, viewer, and training-timeline suites cover mapping, variant resolution, diagnostics, audit, runs, results, assignments, and training transitions | Add result-not-found and remaining training/reference-media error shapes, fixed-fixture output identity, camera-transform/render equivalence, first usable render, playback-start, and seek baselines. |
| Dataset exports | Export controller plus planner, coordinator, writer, history, service, and ExportWizard suites cover reviewed specifications, explicit sources, mappings, missing sources, history, and synchronous compatibility | Add malformed/not-found/error response matrices and controlled planning, writing-throughput, and atomic-finalization baselines. |
| All-tab pipeline and task queue | All-tab controller/overview and worker-boot/task-normalization suites | Add full enabled-stage ordering and payload characterization, partial-stage failure, invalid selection, task cancel-request behavior, and live orchestration timing. |

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

No controlled untouched live baseline has yet been captured for session/overview,
recording media startup/seek/sync/cut, pairing/control/upload, calibration,
detection, triangulation/3D, export, or the full pipeline. No Phase 0 physical
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
