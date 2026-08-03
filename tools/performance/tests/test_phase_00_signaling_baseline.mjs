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
    samples_ms: [5, 1, 4, 2, 3],
    successful_runs: 5,
    measured_runs: 5,
    failure_count: 0,
    failures: [],
    median_ms: 3,
    p50_ms: 3,
    p95_ms: 5,
    minimum_ms: 1,
    maximum_ms: 5,
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

  assert.equal(result.schema_version, 1)
  assert.equal(result.metadata.measured_runs, 1)
  assert.match(result.metadata.evidence_scope, /lower bound only/i)
  assert.deepEqual(result.results.map((item) => item.name), [
    'signaling_receiver_connection_to_viewer_ready',
    'signaling_canonical_control_round_trip',
    'signaling_legacy_control_round_trip',
  ])
  assert.deepEqual(Object.keys(result.metadata.expected_output_identity).sort(), [
    'canonical_device_hello',
    'canonical_device_status',
    'legacy_device_info',
    'legacy_request_device_info',
    'viewer_ready',
  ])
  for (const metric of result.results) {
    assert.equal(metric.measured_runs, 1)
    assert.equal(metric.failure_count, 0)
    assert.deepEqual(metric.failures, [])
    assert.ok(metric.median_ms >= 0)
  }
})
