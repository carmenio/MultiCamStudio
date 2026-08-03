import { execFileSync } from 'node:child_process'
import { cpus, totalmem } from 'node:os'

// Keep the benchmark media identity immutable so a result cannot silently use
// a different set of recordings while retaining the same set-level label.
export const BROWSER_BENCHMARK_FIXTURE = Object.freeze({
  sessionId: 49,
  recordingSetId: 178,
  recordingIds: Object.freeze([649, 650, 651]),
  recordingDurationsSeconds: Object.freeze([196.1, 195.8, 195.766666666667]),
  mediaSizesBytes: Object.freeze([450821959, 445290517, 448855126]),
  calibrationRecordingSetId: 177,
  calibrationId: 113,
  triangulationRunId: 100,
  triangulationMaxFrame: 11_463,
})

// Validate the coupled media fields and return their report representation.
export function createFixtureProvenance(fixture) {
  const recordingIds = [...(fixture.recordingIds ?? [])]
  const recordingDurationsSeconds = [...(fixture.recordingDurationsSeconds ?? [])]
  const mediaSizesBytes = [...(fixture.mediaSizesBytes ?? [])]
  if (
    recordingIds.length === 0
    || recordingDurationsSeconds.length !== recordingIds.length
    || mediaSizesBytes.length !== recordingIds.length
  ) {
    throw new Error('fixture provenance requires one duration and size for every recording')
  }
  if (
    new Set(recordingIds).size !== recordingIds.length
    || recordingIds.some(value => !Number.isInteger(value) || value <= 0)
    || recordingDurationsSeconds.some(value => !Number.isFinite(value) || value <= 0)
    || mediaSizesBytes.some(value => !Number.isInteger(value) || value <= 0)
  ) {
    throw new Error('fixture provenance contains an invalid recording identity or media measurement')
  }
  return Object.freeze({
    recording_ids: Object.freeze(recordingIds),
    recording_duration_seconds: Object.freeze(recordingDurationsSeconds),
    media_sizes_bytes: Object.freeze(mediaSizesBytes),
    camera_count: recordingIds.length,
  })
}

// Construct all fixture-owned report fields together so IDs and media facts
// cannot drift independently in the benchmark payload.
export function createFixtureReportMetadata(fixture) {
  const media = createFixtureProvenance(fixture)
  return Object.freeze({
    fixture: Object.freeze({
      session_id: fixture.sessionId,
      recording_set_id: fixture.recordingSetId,
      recording_ids: media.recording_ids,
      calibration_recording_set_id: fixture.calibrationRecordingSetId,
      calibration_id: fixture.calibrationId,
      triangulation_run_id: fixture.triangulationRunId,
      triangulation_max_frame: fixture.triangulationMaxFrame,
    }),
    camera_count: media.camera_count,
    recording_duration_seconds: media.recording_duration_seconds,
    media_sizes_bytes: media.media_sizes_bytes,
  })
}

// Describe the measured host from runtime values instead of a stale label.
export function describeHardware({ model, logicalProcessorCount, totalMemoryBytes }) {
  return `${model}; ${logicalProcessorCount} logical processors; ${totalMemoryBytes} bytes RAM`
}

// Extract the display name emitted by `powercfg /getactivescheme` on Windows.
export function parseWindowsPowerMode(output) {
  return String(output).match(/\(([^()]+)\)\s*$/)?.[1]?.trim() || null
}

// Collect only read-only host facts; an unavailable power scheme is explicit.
export function discoverRuntimeProvenance() {
  const processors = cpus()
  let powerMode = 'unavailable on this platform'
  if (process.platform === 'win32') {
    try {
      powerMode = parseWindowsPowerMode(
        execFileSync('powercfg.exe', ['/getactivescheme'], { encoding: 'utf8' }),
      ) ?? 'unavailable: active Windows power scheme was not parseable'
    } catch (error) {
      const reason = error instanceof Error ? error.message.split(/\r?\n/, 1)[0] : String(error)
      powerMode = `unavailable: ${reason}`
    }
  }
  return Object.freeze({
    hardware: describeHardware({
      model: processors[0]?.model?.trim() || 'unknown CPU',
      logicalProcessorCount: processors.length,
      totalMemoryBytes: totalmem(),
    }),
    power_mode: powerMode,
  })
}

// Record the exact production-build and browser launch contract used by the runner.
export function createBuildProvenance({ viteEdgeMode, viteApiUrl, previewPort, chromeArguments }) {
  return Object.freeze({
    build_mode: 'Vite production build served by vite preview; headed Chrome with GPU enabled',
    build_environment: Object.freeze({
      VITE_EDGE_MODE: String(viteEdgeMode),
      VITE_API_URL: String(viteApiUrl),
    }),
    preview_port: Number(previewPort),
    chrome_arguments: Object.freeze([...chromeArguments]),
  })
}
