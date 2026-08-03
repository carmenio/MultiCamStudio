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
- Signaling initial baseline: 10 passed, 1 skipped. The current suite is 11
  passed with real WebM-to-MP4 FFmpeg execution and no skip.
- Full backend: 519 passed.
- Full operator web: 657 passed; production build passed.
- EdgeRelay: 43 passed.
- Camera mobile: 53 passed; type-check and native-patch validation passed.

After the latest characterization additions, the complete backend suite passes
640 tests. This includes the 23-test capture lifecycle/concurrency suite, the
16-test sessions response suite, focused media and 3D error/transform cases,
the expanded cut validation/ffmpeg contract matrix, and persistent
task-store/worker lifecycle cases. The complete operator suite
passes with the repository's bounded-worker
command and includes 7 new RecordingPage contract tests (664 total); its
production build also passes. The expanded EdgeRelay suite passes 57 tests.
Existing React `act(...)`, duplicate-key,
missing-Expo-base-config, and large-chunk warnings remain baseline noise.

One high-severity npm advisory is present in the signaling dependency tree. It is
not changed in this refactor because an upgrade requires a separate compatibility
and security review.

### Reproducible gate commands

Run these commands from the stated working directory. The operator suite uses
bounded workers because unconstrained parallelism has an established timeout
failure mode unrelated to application behavior.

| Gate | Working directory | Command |
| --- | --- | --- |
| Complete backend | `pc/services/backend` | `python -m pytest Tests -q` |
| Operator tests | `laptop/apps/operator-web` | `npm run test:run -- --maxWorkers=4` |
| Operator production build | `laptop/apps/operator-web` | `npm run build` |
| EdgeRelay | `laptop/services/edge-relay` | `python -m pytest tests -q` |
| Signaling | `laptop/services/signaling` | `npm test` |
| Camera mobile tests | `laptop/apps/camera-mobile` | `npm test` |
| Camera mobile type-check | `laptop/apps/camera-mobile` | `npx tsc --noEmit` |
| Native patch contract | `laptop/apps/camera-mobile` | `npm run validate:native-patch` |
| Python performance harness | repository root | `python -m pytest tools/performance/tests -q` |
| Browser/signaling harness | repository root | `node --test tools/performance/browser/tests/*.test.mjs tools/performance/tests/test_phase_00_signaling_baseline.mjs` |

Run Ruff and diff checks on the files touched by each commit. The operator's
repository-wide lint still contains legacy failures, so it is not reported as a
clean gate.

## Characterization coverage and gaps

The following matrix is the traceability baseline for extraction work. A green
automated suite does not close a listed live, performance, browser, or physical
device gap.

| Contract family | Current characterization evidence | Gap that must be closed before the owning extraction is accepted |
| --- | --- | --- |
| Sessions | Sixteen focused controller tests freeze exact successful UI/full bodies, integer-key JSON stringification, profile-specific adapter calls, and the current injected PostgREST `54000` failure as the exact outward HTTP 500 envelope; operator session persistence and SessionResourceContext suites cover consumers. | A live session/overview pair is captured, but the current full profile remains HTTP 500 and database/OS-cold evidence is unavailable. |
| Cameras and pairing | `test_session_cameras_controller.py`; Filming camera/page suites; camera-mobile config, signaling, selection, and pairing-presentation suites. Eleven focused EdgeRelay cases freeze both issue aliases, signed claims, exact issue/resolve errors, the current invalid-session HTML 500, ISO expiry, ignored fields, room/label fallbacks, token tamper/expiry, forwarded origins, full success payload, and resolve-after-cache-deletion behavior. Deterministic production-route baselines freeze PC HMAC and EdgeRelay timed-serializer token issue/resolve/round-trip latency, cache behavior, forwarded-origin URLs, and semantic identities. | Live nginx/TLS/QR plus physical iOS/Android pairing, reconnect, certificate, and transport-mismatch recovery remain unavailable. |
| Recording media and playback source | Recording controller tests cover original, synchronized, and preview media headers; byte ranges and exact `206`/`Content-Range` behavior; exact missing-file responses; adaptive headers, traversal rejection, file-scheme fallback, original/synced selection, preview precedence, HLS-ready/warmup paths, missing local media, and the `200` warning fallback after database or adaptive-preparation failures. The expanded cut matrix freezes validation, normalization, exact task payloads, production ffmpeg defaults/commands, error propagation, nonfatal metadata persistence, cancellation boundaries, partial cleanup, and post-persistence rollback. Playback hooks, cache, timeline, and viewer suites cover browser orchestration. A real three-camera browser run captures cold preview startup, first decoded frame, and synchronized playback start; a deterministic full-handler baseline captures warm three-camera transcoding, probing, persistence, progress, and preview enqueue with complete per-sample output identities and deployed-setting parity. | Multi-camera seek readiness currently times out after 20 seconds and is retained as unavailable; cold cutting and live database/worker cut orchestration remain unmeasured. |
| Playback-session lifecycle | Ten focused route tests cover create validation, all-row and filtered selection, database ordering, distinct empty-result errors, signaling precedence/fallback, five offset aliases, direct/probed/zero duration, join tokens, stats, and repeated delete | The extraction is an early Phase 1 slice, not Phase 0 completion. Cold-cache and browser-consumer evidence remain unavailable. |
| Resumable and multipart uploads | Recording controller tests cover required fields, sorted resume state, chunk index behavior, checksum conflict/mismatch, incomplete and missing chunks, partial-output retention, repeated completion/collision suffixes, post-assembly persistence failure, task enqueueing, imported signaling files, and finalize partial/all-failure behavior. They also freeze that recording-upload and preview-build tasks do not poll running cancellation requests. A deterministic production-route baseline captures server initialization/resume plus 16 MiB chunk-write and assembly/checksum throughput with exact output identity. | Physical Stop-to-upload-init and interrupted-network recovery remain unavailable; current permissive out-of-range index, repeated-completion, and noncooperative upload/preview cancellation behavior are frozen until separately changed. |
| Capture sessions | Twenty-three focused tests cover start/create/reuse, no-active and stale-active behavior, owner-protected status/PATCH/stop/abort, unknown state and invalid snapshot normalization, repeatable abort, idempotent finalize, no-success and all-import-failed completion, empty-set cleanup, shared ingest, partial import, invalid session identity, unexpected finalize errors, and concurrent finalization. One controller serializes and returns the same persisted response; separate controllers sharing persistence can both create/import distinct sets and the last write wins. | The multi-worker duplicate-finalize race is frozen as an existing defect. Physical Stop-to-upload-init and interrupted-network validation remain unavailable. |
| EdgeRelay, host storage, and Edge-to-PC sync | The 57-test `test_edge_relay.py` suite covers caching, storage selection, host-agent transfer, resumable and legacy upload, deletion guards, capture start/finalize recovery, complete pairing contracts, stop/status/abort shapes, selected transfer start plus pause/retry transitions, and generic/viewer proxy preservation. It freezes the current compatibility behavior where stop/abort of an unknown capture return `200` and those routes do not reject a different supplied owner. The 17-test `test_edge_recording_repair.py` suite additionally freezes PC bearer authorization, capture and recording initialization, duplicate/conflicting chunks, chunk validation, capture finalize/status shapes, completion, repair, and preview enqueueing. | Add live host-folder transfer/recovery evidence. |
| Signaling and legacy browser phone | Eleven signaling smoke/config cases execute real WebM-to-MP4 FFmpeg conversion and cover upload/download, container signature, extension rules, room isolation, viewer rejoin, and legacy control mapping; browser-phone source contract tests cover IndexedDB and active compatibility markers. A real production-relay loopback baseline freezes receiver readiness plus canonical and legacy round-trip latency and exact normalized message identities. | TLS/LAN/WebRTC and physical browser-phone recording/upload recovery remain unmeasured. |
| Calibration | Controller, database, generator, service, viewer, and viewer-renderer suites; Calibration page/component/flow suites. Deterministic controller/service cases freeze pre-start, post-solver, and late cancellation, including batch/run divergence and retained artifact boundaries. Live viewer metadata and batch status are captured. Separate deterministic baselines cover four-camera metadata/first-frame preflight, seeded two-camera FreeMoCap processing, ten-camera HTML rendering, and canonical browser Plotly readiness with complete output identities. | Add full batch orchestration/live task evidence; pure processing and cancellation boundaries are frozen. |
| Point detection and post-processing | Controller, catalog database, result persistence, service, post-processing pipeline, segmenter, API, scheduler, hydration, page, sidebar, and toolbar suites. Six task cases freeze pre-run, model-progress, late raw, pre-stage, intra-stage, and next-stage cancellation with exact retained artifacts/checkpoint chains. Live summary and first/seeked/sequential window retrieval are captured. A deterministic three-camera, 60-second production-code baseline covers all six ordered post-processing stages and 36 five-second segment outputs with full canonical equivalence hashes. | Live overlay equivalence remains absent; post-processing persistence/task dispatch is not included in the pure processing timing. |
| Triangulation and 3D | Controller, service, database, API, page, viewer, and training-timeline suites cover mapping, variant resolution, diagnostics, audit, runs, results, assignments, training transitions, cancellation boundaries, exact missing-run/result/training/reference-media errors, and storage failures. A non-identity projection fixture freezes exact `K @ [R|t]` world-to-camera output without mutating calibration input. A deterministic production-service baseline triangulates 81,000 observations into 27,000 accepted points with fixed identities; the browser run freezes first usable render, seek, playback, and canvas identity. | Live rendered-skeleton/camera-transform equivalence remains unavailable; service-side projection equivalence is frozen. |
| Dataset exports | The 17-test controller suite plus planner, coordinator, writer, history, service, and ExportWizard suites cover reviewed specifications, explicit sources, mappings, missing sources, history, and synchronous compatibility. Exact route contracts include validation and unexpected preflight errors, missing task service, stale reviews, zero eligible sets, numeric/opaque missing-job lookups, pre-start/between-set/in-range/late cancellation, partial cleanup, and atomic-finalization precedence. A production preflight baseline captures an eligible fixed-source plan with stable semantic and review hashes. A separate fixed three-camera `two_d_3d` baseline exercises production artifact writing, checksums, manifest integrity, and atomic finalization across five measured exports with stable output identity. | Live server-side export task dispatch and history polling remain uncaptured; writer/finalization throughput and cancellation boundaries are frozen. |
| All-tab pipeline and task queue | Twenty-five focused route tests freeze task list/detail filtering and shaping, queued cancellation, running cancel requests, completed cleanup, persistent-store fallback, five-stage order, exact task payloads, dependency chaining, duplicate-sync reuse, sync-disabled skipping, per-set calibration linking, validation errors, adapter unavailability, and partial task-creation failure. Eight deterministic PostgREST-adapter tests freeze persistent create/list/claim/dependency/cascade/progress/terminal/cancel/orphan/cleanup semantics; four fallback-store tests freeze corresponding dependency and cancellation behavior. Six bounded TaskService cases freeze progress/result forwarding, handler errors/cancellation, start/stop idempotence, and the current persistent-to-memory startup fallback. Worker-boot cases freeze the complete 11-handler registry, strict/non-strict missing-handler behavior, signal registration, and clean entrypoint exit. The Activity flyout now freezes queued cancellation versus running cancel-request dispatch. Overview service and worker/task-normalization suites retain stage precedence and dispatch behavior. A deterministic ten-set route benchmark captures exact five-stage task-chain construction. | Add live dedicated-stack worker orchestration timing. Current validation-before-stage-selection, nontransactional partial effects, 200-row claim window, database/fallback differences, and silent worker-store fallback are documented baseline behaviors. |

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
three-camera preview startup, first decoded frame, synchronized playback start,
3D first usable render/timeline seek/playback start, and live calibration Plotly
readiness. It does not cover database/operating-system cold state, reliable
multi-camera recording seeking, live database/worker cutting, Edge control, physical upload,
live export task dispatch, or full-pipeline worker execution. Deterministic PC upload
route/filesystem behavior and production export writing/finalization are captured
independently of the live database and configured export root. The production
cut handler is also captured with real three-camera ffmpeg processing and
deterministic infrastructure adapters. No Phase 0 physical
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
- Keep `tools/performance/phase_00_required_scenarios.json` current as blockers
  close. The committed-evidence gate rejects malformed, failed, or regressed
  reports while the registry separately prevents well-formed `unavailable` or
  partial scenarios from being represented as phase completion.
- Run ten maximum-profile recordings plus interrupted-network recovery on both
  a physically connected iPhone and Android device. This must include real QR,
  certificate, signaling, preview, asynchronous Stop-to-upload-init, upload,
  background/foreground, Dynamic Type, and font-scaling evidence. No ADB device
  is available on the current host; the paired iPhone is Bluetooth-only and is
  not an executable development-client connection.
- Use a dedicated disposable database/Compose project to capture persistent
  backend-to-worker task pickup, terminal state, cooperative cancellation, and
  live export dispatch/history without mutating the operator database.
- Capture live host-folder transfer/recovery, nginx/TLS pairing, reliable
  all-camera seek, synchronization processing, cold recording cutting, overlay
  equivalence, and explicit 3D camera-transform equivalence.
- Stabilize the production browser benchmark. Resource-quiet preview setup and
  disabled Chrome background throttling removed a measured prefetch confounder,
  and the long 3D/Plotly scenarios now repeat within the 3% band. Consecutive
  controlled captures still exceed the band for several short-operation p95s,
  so the browser report is not yet a reliable before/after gate despite having
  valid raw samples and output identities.
- The full sessions profile remains HTTP 500 on the current snapshot; its exact
  outward body is frozen with an injected `54000` adapter failure.
- An early playback-session extraction exists only on dangling history and is
  not an ancestor of the active PC revision. Phase 1 structural work remains
  paused and its earlier evidence does not substitute for the Phase 0 matrix.
