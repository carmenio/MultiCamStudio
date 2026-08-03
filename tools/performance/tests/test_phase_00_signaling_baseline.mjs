import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  normalizedMessageIdentity,
  runSignalingBenchmark,
  stableStringify,
  summarizeSamples,
} from '../phase_00_signaling_baseline.mjs'

test('summarizeSamples reports median, nearest-rank p95, and bounds', () => {
  assert.deepEqual(summarizeSamples([5, 1, 4, 2, 3]), {
    median_ms: 3,
    p95_ms: 5,
    min_ms: 1,
    max_ms: 5,
    failures: 0,
    measured_runs: 5,
  })
})

test('message identities ignore correlation tokens but retain protocol fields', () => {
  const first = { type: 'device.hello', roomId: 'room', protocolVersion: 2, benchmarkCorrelationId: 'a' }
  const second = { protocolVersion: 2, benchmarkCorrelationId: 'b', roomId: 'room', type: 'device.hello' }
  assert.equal(stableStringify(first), stableStringify({ ...first }))
  assert.equal(normalizedMessageIdentity(first), normalizedMessageIdentity(second))
  assert.notEqual(
    normalizedMessageIdentity(first),
    normalizedMessageIdentity({ ...second, protocolVersion: 1 }),
  )
})

test('production signaling benchmark preserves canonical and legacy normalization', async () => {
  const result = await runSignalingBenchmark({ warmupRuns: 0, measuredRuns: 1, writeResult: false })

  assert.equal(result.metadata.measured_runs, 1)
  assert.match(result.metadata.scope, /lower bound only/i)
  assert.deepEqual(Object.keys(result.metrics).sort(), [
    'canonical_device_hello_status_round_trip_ms',
    'legacy_device_info_round_trip_ms',
    'receiver_connection_to_viewer_ready_ms',
  ])
  assert.deepEqual(Object.keys(result.normalized_message_identities).sort(), [
    'canonical_device_hello',
    'canonical_device_status',
    'legacy_device_info',
    'legacy_request_device_info',
    'viewer_ready',
  ])
  for (const metric of Object.values(result.metrics)) {
    assert.equal(metric.measured_runs, 1)
    assert.equal(metric.failures, 0)
    assert.ok(metric.median_ms >= 0)
  }
})
