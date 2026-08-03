import assert from 'node:assert/strict'
import test from 'node:test'

import {
  BROWSER_BENCHMARK_FIXTURE,
  createBuildProvenance,
  createFixtureProvenance,
  createFixtureReportMetadata,
  describeHardware,
  parseWindowsPowerMode,
} from '../provenance.mjs'

test('browser fixture provenance freezes the three production recording identities', () => {
  assert.deepEqual(BROWSER_BENCHMARK_FIXTURE.recordingIds, [649, 650, 651])
  assert.equal(Object.isFrozen(BROWSER_BENCHMARK_FIXTURE), true)
  assert.equal(Object.isFrozen(BROWSER_BENCHMARK_FIXTURE.recordingIds), true)

  const provenance = createFixtureProvenance(BROWSER_BENCHMARK_FIXTURE)
  assert.deepEqual(provenance.recording_ids, [649, 650, 651])
  assert.deepEqual(provenance.recording_duration_seconds, [196.1, 195.8, 195.766666666667])
  assert.deepEqual(provenance.media_sizes_bytes, [450821959, 445290517, 448855126])
  assert.equal(provenance.camera_count, 3)
})

test('browser report metadata carries recording IDs alongside the set identity', () => {
  const metadata = createFixtureReportMetadata(BROWSER_BENCHMARK_FIXTURE)
  assert.deepEqual(metadata.fixture.recording_ids, [649, 650, 651])
  assert.equal(metadata.fixture.recording_set_id, 178)
  assert.equal(metadata.camera_count, 3)
  assert.deepEqual(metadata.media_sizes_bytes, [450821959, 445290517, 448855126])
})

test('fixture provenance rejects incomplete media identity', () => {
  assert.throws(
    () => createFixtureProvenance({
      recordingIds: [649, 650, 651],
      recordingDurationsSeconds: [196.1],
      mediaSizesBytes: [450821959, 445290517, 448855126],
    }),
    /one duration and size for every recording/,
  )
})

test('hardware provenance is derived from the runtime rather than a checked-in label', () => {
  assert.equal(
    describeHardware({ model: 'Fixture CPU', logicalProcessorCount: 8, totalMemoryBytes: 16_000 }),
    'Fixture CPU; 8 logical processors; 16000 bytes RAM',
  )
})

test('Windows active power scheme parser returns its configured display name', () => {
  assert.equal(
    parseWindowsPowerMode('Power Scheme GUID: 00000000-0000-0000-0000-000000000000  (High performance)'),
    'High performance',
  )
  assert.equal(parseWindowsPowerMode('unexpected output'), null)
})

test('build provenance records the production routing and browser launch contract', () => {
  assert.deepEqual(
    createBuildProvenance({
      viteEdgeMode: 'false',
      viteApiUrl: 'https://127.0.0.1:5000',
      previewPort: 4173,
      chromeArguments: ['--window-size=1440,1000', 'about:blank'],
    }),
    {
      build_mode: 'Vite production build served by vite preview; headed Chrome with GPU enabled',
      build_environment: {
        VITE_EDGE_MODE: 'false',
        VITE_API_URL: 'https://127.0.0.1:5000',
      },
      preview_port: 4173,
      chrome_arguments: ['--window-size=1440,1000', 'about:blank'],
    },
  )
})
