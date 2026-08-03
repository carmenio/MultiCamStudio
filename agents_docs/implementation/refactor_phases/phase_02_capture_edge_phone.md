# Phase 2: Capture, Edge, Signaling, and Phone Clients

## Status

Pending Phase 1 acceptance. No structural changes have started.

## Frozen interfaces

Pairing tokens and QR values, session-camera routes, canonical and legacy
signaling messages, capture lifecycle states, resumable upload requests, transfer
retries, EdgeRelay proxy paths, pending-footage storage, Expo Router ownership,
and the active browser-phone URL remain observable contracts.

## Intended ownership and data flow

EdgeRelay will compose deep capture, upload, transfer, storage, cache, and proxy
modules. Filming and phone screens will compose a long-lived runtime plus focused
workflow hooks. New seams must be justified by production and deterministic test
adapters; protocol translation stays at the boundary.

## Acceptance evidence required

Characterization must cover pairing through cleanup, including interrupted
transfers. Benchmarks must include pairing/control, preview readiness,
Stop-to-upload-init, throughput, reconnect, and retry. Acceptance additionally
requires ten maximum-profile recordings and interrupted-network recovery on a
physical iPhone and Android device.

## Rollback

Revert internal callers to the existing EdgeRelay, Filming, Expo runtime, and
browser-phone implementations. No route, stored key, file layout, or message
migration is permitted.
