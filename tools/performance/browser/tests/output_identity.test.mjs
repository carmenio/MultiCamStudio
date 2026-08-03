import assert from 'node:assert/strict'
import test from 'node:test'

import { hashOperatorShellSignature } from '../output_identity.mjs'

const POPULATED_SHELL = JSON.stringify({
  shellMode: 'desktop',
  navigation: ['Recordings', 'Calibration'],
  sessions: ['Benchmark session'],
  activeMain: 'app-main',
})

test('operator shell identity is stable for the same populated shell', () => {
  assert.equal(
    hashOperatorShellSignature(POPULATED_SHELL),
    hashOperatorShellSignature(POPULATED_SHELL),
  )
})

test('operator shell identity rejects a direct viewer page', () => {
  assert.throws(
    () => hashOperatorShellSignature(JSON.stringify({ navigation: [], sessions: [] })),
    /requires populated navigation, sessions, and main content/,
  )
})

test('operator shell identity rejects malformed evidence', () => {
  assert.throws(() => hashOperatorShellSignature('not JSON'), /was not valid JSON/)
})
