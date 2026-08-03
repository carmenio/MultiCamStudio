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

One high-severity npm advisory is present in the signaling dependency tree. It is
not changed in this refactor because an upgrade requires a separate compatibility
and security review.

## Rollback

Revert the test-fixture and expectation commits. No runtime code, schema, stored
data, or deployment configuration is changed by these baseline repairs.

## Remaining work

- Complete and validate the reusable performance harness.
- Capture the required live workflow baselines.
