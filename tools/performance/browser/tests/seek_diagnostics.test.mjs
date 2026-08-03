import assert from 'node:assert/strict'
import test from 'node:test'

import { formatRecordingSeekDiagnostic } from '../seek_diagnostics.mjs'

test('seek diagnostics identify every source and its terminal outcome', () => {
  assert.equal(
    formatRecordingSeekDiagnostic([
      { index: 0, source: 'recording-649.mp4', readyState: 4, currentTime: 20, outcome: 'seeked' },
      { index: 1, source: 'recording-650.mp4', readyState: 2, currentTime: 10, outcome: 'timeout' },
    ]),
    'camera[0] source="recording-649.mp4" readyState=4 currentTime=20 outcome=seeked; '
      + 'camera[1] source="recording-650.mp4" readyState=2 currentTime=10 outcome=timeout',
  )
})

test('seek diagnostics retain explicit unknown values', () => {
  assert.equal(
    formatRecordingSeekDiagnostic([{ index: 0, source: '', outcome: 'error' }]),
    'camera[0] source="unknown" readyState=unknown currentTime=unknown outcome=error',
  )
})
