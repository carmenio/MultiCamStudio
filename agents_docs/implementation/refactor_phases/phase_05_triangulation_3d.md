# Phase 5: Triangulation and 3D

## Status

Pending Phase 4 acceptance. No structural changes have started.

## Frozen interfaces

Variant precedence, legacy fallback, calibration resolution, camera mapping,
confidence normalization, diagnostics, skeleton metadata, task payloads, errors,
and response bodies remain unchanged.

## Intended ownership and data flow

Variant resolution, calibration context, audit generation, and task orchestration
will become focused workflow modules. ThreeD-page orchestration will compose
viewer lifecycle, synchronized playback, timeline, settings, and presentation.

## Acceptance evidence required

Fixed-fixture tests and benchmarks cover triangulation, result retrieval, first
usable render, playback start, and seeking. Camera transforms and rendered
skeletons require equivalence evidence.

## Rollback

Redirect callers to the existing controller and page implementations. No result,
assignment, calibration, training-segment, or client-state migration is allowed.
