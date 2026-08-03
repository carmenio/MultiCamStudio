# Phase 7: Cross-Cutting Cleanup and Final Hardening

## Status

Pending Phase 6 acceptance. No cross-cutting cleanup has started.

## Allowed cleanup

Descriptive internal renames proceed one symbol family per commit. Duplicate or
dead implementations are removed only after equivalence is proven; external
compatibility shims remain. Catch-all modules may be replaced by deep workflow
modules, never generic utility collections or pass-through classes.

## Acceptance evidence required

Run the complete automated, live, physical-device, output-equivalence, build,
type-check, compilation, and performance matrices. The final performance report
must compare every Phase 0 baseline with the final implementation and distinguish
unchanged noise from a measured improvement.

## Documentation and rollback

Record final names, removals, retained shims, verified limitations, reusable
lessons, and per-commit rollback points. Refresh Graphify after the final code
state. No cleanup commit may require a data migration to revert.
