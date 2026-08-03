# Phase 3: Calibration

## Status

Pending Phase 2 acceptance. No structural changes have started.

## Frozen interfaces

Configuration normalization, synchronization validation, batch task payloads,
FreeMoCap defaults, partial-camera behavior, persistence fields, status/error
responses, and database-rendered viewer output remain unchanged.

## Intended ownership and data flow

One calibration workflow will own orchestration behind injected persistence,
media, runner, and task adapters. HTTP controllers and Calibration-page modules
will remain composition boundaries for configuration, cards, progress, and viewer
presentation.

## Acceptance evidence required

Characterization covers normalization through viewer rendering. Fixed-fixture
benchmarks cover preflight, batch creation, processing, polling, and viewer
generation, with rendered output equivalence and live validation recorded here.

## Rollback

Redirect controller and UI callers to the current implementation. No database,
task, viewer URL, or solver-configuration migration is permitted.
