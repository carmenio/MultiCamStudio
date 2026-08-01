# Operator web design system

Status: active implementation contract  
Surface: `laptop/apps/operator-web`

## Ownership

- `src/styles/tokens.css` is the only owner of interface colors, typography, spacing, control heights, motion, radii, focus, and shadow values.
- `src/styles/visualizationPalette.ts` and `src/styles/visualization-palette.css` own media, pose-overlay, calibration, and Three.js colors. Visualization colors must not be reused for application chrome.
- `src/components/shared_ui/Controls.tsx` owns labelled buttons, icon buttons, and keyboard-visible tooltips.
- `src/components/shared_ui/StatusSurface.tsx` owns semantic status labels and icons.
- `src/styles/foundation.css` owns shared component styling and the temporary compatibility bridge for legacy page selectors.

## Visual contract

- The operator is dark-only: neutral studio-console surfaces with one purple interaction accent.
- Space Grotesk is the interface font. The technical monospace token is limited to code, paths, timestamps, durations, frame counts, progress, and similar machine values.
- Visible text uses the 12, 14, 16, 20, and 24 px scale. Essential text must never render below 12 px.
- Familiar utilities may be icon-only, but must use Feather icons through `react-icons/fi`, a required accessible label, and a tooltip visible on hover and keyboard focus.
- Workflow navigation, primary workflow actions, confirmations, and unfamiliar actions retain visible labels.
- Status and selection never rely on color alone; pair semantic color with an icon, label, shape, or marker.

## Right-sidebar density

- Treat right sidebars as compact property inspectors across Capture, Recordings, Calibration, Point Detection, and 3D.
- Use the shared 4 px internal and 8 px section spacing rhythm, with `--control-height-dense` for compact controls. Avoid adding page-specific padding that expands shared sidebar primitives.
- Prefer one cohesive property surface with aligned label/control rows over a separate padded card for every field. Use subtle separators to preserve scanability.
- Keep section disclosure, keyboard focus, accessible labels, disabled states, and collapsed-rail actions intact when condensing a sidebar.
- Sidebar density changes must reuse the interface typography, surface, border, radius, focus, and interaction tokens; they must not introduce a separate visual theme.

## Legacy migration rule

`App.css` still contains historical page-level declarations. New raw colors, font families, and arbitrary sub-12 px sizes are prohibited. Migrate touched selectors to tokens or shared primitives, and keep the compatibility bridge until the remaining page styles can be split by subsystem. The design-system contract test prevents this debt from growing.

## Validation

Run `npm run test:run`, `npm run lint`, and `npm run build` from `laptop/apps/operator-web`. The design-system contract tests verify token ownership, the typography floor, library-backed icons, and the absence of raw colors in canonical component styles.
