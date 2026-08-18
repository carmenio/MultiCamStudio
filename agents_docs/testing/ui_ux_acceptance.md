# UI/UX acceptance checks

## Automated checks

Last verified on 2026-07-30:

- Operator production build: passed (189 modules transformed).
- Operator tests: 84 files passed, 622 tests passed.
- Phone TypeScript: passed.
- Phone service, route, and presentation tests: 14 files passed, 53 tests passed.
- Native shared-capture patch validation: passed (`ios-finalization-v2`).
- Android Expo export: passed.

The repository-wide operator ESLint command is not an acceptance gate for this package yet. It still reports legacy React Compiler rules and test-only explicit-any violations across the existing application; build, TypeScript, and executable tests are green.

Run operator checks from `laptop/apps/operator-web`:

```powershell
npm run test:run
npm run build
```

Run phone checks from `laptop/apps/camera-mobile`:

```powershell
npx tsc --noEmit
npm test
npm run validate:native-patch
npx expo export --platform android --output-dir .expo-export-validation
```

## Desktop manual matrix

Validate 1920 x 1080, 1600 x 900, 1366 x 768, 1100 x 700, and 1024 x 768 plus 200% browser zoom.

- Pane transitions preserve sessions, expanded rows, selected session, and selected recording set.
- At 1366 x 768 the center task remains dominant and the primary toolbar action remains visible.
- Constrained panes are mutually exclusive overlays; closing a pane restores focus to its toggle.
- Every workflow distinguishes loading, empty, stale/partial, recoverable failure, and blocking failure.
- Keyboard focus, tooltips, menus, dialogs, selection, reduced motion, contrast, and target sizes remain usable.
- One failed recording camera preserves playback and retry for unaffected cameras.

## Phone manual matrix

Validate approximately 375 x 812 and 430 x 932 on rebuilt iOS and Android development clients.

- QR/deep-link pairing follows Scan, Permissions, conditional Trust, and Connected without exposing manual infrastructure by default.
- Camera and Recordings are the only connected tabs; Settings and camera details open as secondary routes.
- Route and tab changes do not disconnect signaling or stop/finalize recording.
- Recording, finalizing, uploading, ready, and failed states use text plus shape/icon and accessible announcements.
- Pending recordings survive restart; interrupted upload resumes without duplication; active uploads cannot be deleted.
- Historical failures do not replace the newest recording status.
- Safe areas, Dynamic Type/font scaling, background/foreground transitions, and ten maximum-profile recording stops pass on device.
## Run Pipeline automatic discovery

- Auto-find is off by default. Enabling it forces Sync and Calibration on while leaving downstream analysis stages configurable.
- Entering Review scans all recording sets in every represented session and exposes progress, elapsed time, retry, chronological roles, evidence, links, and exact task paths.
- Completed calibrations and valid links are authoritative; unknown sets use bounded distributed multi-camera board sampling.
- Partial evidence, unreadable media, insufficient cameras, missing preceding calibration, and stale plans block submission until corrected or rescanned.
- Calibration sets queue only Sync and Calibration. Analysis sets queue Sync plus enabled downstream stages and depend on the selected calibration's successful completion.
- Calibration links are absent before success, written before dependents run, and remain absent when calibration fails or is canceled.
