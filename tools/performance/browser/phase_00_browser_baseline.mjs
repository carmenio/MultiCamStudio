// Production-build browser benchmark for shell readiness and workflow navigation.
import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { performance } from 'node:perf_hooks'

import { CdpClient, summarizeSamples, waitFor } from './cdp_client.mjs'
import { hashOperatorShellSignature } from './output_identity.mjs'
import {
  BROWSER_BENCHMARK_FIXTURE,
  createBuildProvenance,
  createFixtureProvenance,
  createFixtureReportMetadata,
  discoverRuntimeProvenance,
} from './provenance.mjs'
import { formatRecordingSeekDiagnostic } from './seek_diagnostics.mjs'

const REPOSITORY_ROOT = resolve(import.meta.dirname, '..', '..', '..')
const OPERATOR_ROOT = join(REPOSITORY_ROOT, 'laptop', 'apps', 'operator-web')
const VITE_ENTRYPOINT = join(OPERATOR_ROOT, 'node_modules', 'vite', 'bin', 'vite.js')
const TYPESCRIPT_ENTRYPOINT = join(OPERATOR_ROOT, 'node_modules', 'typescript', 'bin', 'tsc')
const OPERATOR_ORIGIN = 'http://127.0.0.1:4173'
const PREVIEW_PORT = 4173
const DEBUG_PORT = 9223
const FIXTURE_PROVENANCE = createFixtureProvenance(BROWSER_BENCHMARK_FIXTURE)
const FIXTURE_REPORT_METADATA = createFixtureReportMetadata(BROWSER_BENCHMARK_FIXTURE)
const SESSION_ID = String(BROWSER_BENCHMARK_FIXTURE.sessionId)
const RECORDING_SET_ID = String(BROWSER_BENCHMARK_FIXTURE.recordingSetId)
const CALIBRATION_RECORDING_SET_ID = String(BROWSER_BENCHMARK_FIXTURE.calibrationRecordingSetId)
const CALIBRATION_ID = String(BROWSER_BENCHMARK_FIXTURE.calibrationId)
const TRIANGULATION_RUN_ID = String(BROWSER_BENCHMARK_FIXTURE.triangulationRunId)
const TRIANGULATION_MAX_FRAME = BROWSER_BENCHMARK_FIXTURE.triangulationMaxFrame
const EXPECTED_CAMERA_COUNT = FIXTURE_PROVENANCE.camera_count
// Browser/GPU/media caches need more than the universal minimum to converge
// across isolated Chrome processes. Twenty samples also keep nearest-rank p95
// from degenerating to the single maximum observed value.
const WARMUP_RUNS = 10
const MEASURED_RUNS = 20
const READINESS_TIMEOUT_MS = 20_000
const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const OUTPUT_PATH = join(
  REPOSITORY_ROOT,
  'tools',
  'performance',
  'results',
  'phase_00_browser',
  'phase_00_browser_baseline.json',
)

const FIRST_USABLE_EXPRESSION = `Boolean(
  document.querySelector('.app.app-shell') &&
  document.querySelector('nav[aria-label="Primary"]') &&
  document.querySelector('.workspace') &&
  document.querySelector('.tree-item.session-row') &&
  !document.querySelector('.sidebar [role="status"]') &&
  !document.querySelector('.unsupported-shell-notice')
)`

// Launch a child process without a shell so paths and arguments remain literal.
function launch(command, args, options = {}) {
  return spawn(command, args, { stdio: 'ignore', windowsHide: true, ...options })
}

async function runProcess(command, args, options = {}) {
  await new Promise((resolveRun, rejectRun) => {
    const child = launch(command, args, options)
    child.once('error', rejectRun)
    child.once('exit', (code) => {
      if (code === 0) resolveRun()
      else rejectRun(new Error(`${command} exited with code ${code}`))
    })
  })
}

async function waitForHttp(url) {
  await waitFor(async () => {
    try {
      return (await fetch(url)).ok
    } catch {
      return false
    }
  }, READINESS_TIMEOUT_MS, 100)
}

async function waitForStage(stageName, predicate, timeoutMs = READINESS_TIMEOUT_MS) {
  try {
    await waitFor(predicate, timeoutMs)
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    throw new Error(`${stageName}: ${detail}`)
  }
}

async function openCdpTarget() {
  await waitForHttp(`http://127.0.0.1:${DEBUG_PORT}/json/version`)
  const response = await fetch(
    `http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent('about:blank')}`,
    { method: 'PUT' },
  )
  if (!response.ok) throw new Error(`Chrome target creation failed: ${response.status}`)
  const target = await response.json()
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolveOpen, rejectOpen) => {
    socket.addEventListener('open', resolveOpen, { once: true })
    socket.addEventListener('error', rejectOpen, { once: true })
  })
  return new CdpClient(socket)
}

async function evaluate(client, expression, awaitPromise = false) {
  let result
  try {
    result = await client.send('Runtime.evaluate', {
      expression,
      awaitPromise,
      returnByValue: true,
    })
  } catch (error) {
    throw new Error(`browser evaluation failed for ${expression.slice(0, 80)}: ${error.message}`)
  }
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description
      ?? result.exceptionDetails.exception?.value
      ?? result.exceptionDetails.text
      ?? 'unknown browser exception'
    throw new Error(`browser expression failed: ${detail}`)
  }
  return result.result?.value
}

async function navigate(client, url) {
  await client.send('Page.navigate', { url })
  await waitFor(
    async () => (await evaluate(client, 'document.readyState')) === 'complete',
    READINESS_TIMEOUT_MS,
  )
}

async function waitForUsableShell(client) {
  await waitFor(
    async () => Boolean(await evaluate(client, FIRST_USABLE_EXPRESSION)),
    READINESS_TIMEOUT_MS,
  )
  await evaluate(
    client,
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    true,
  )
}

async function prepareOrigin(client) {
  await navigate(client, OPERATOR_ORIGIN)
  await evaluate(
    client,
    `localStorage.setItem('multicam:selectedSessionId', ${JSON.stringify(SESSION_ID)})`,
  )
}

// Open a workflow from the primary navigation and wait for its overview grid.
async function openWorkflow(client, label, gridSelector) {
  const clicked = await evaluate(client, `(() => {
    const button = [...document.querySelectorAll('nav[aria-label="Primary"] button')]
      .find(item => item.textContent?.trim() === ${JSON.stringify(label)})
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!clicked) throw new Error(`${label} navigation button was not found`)
  await waitFor(
    async () => Boolean(await evaluate(client, `Boolean(document.querySelector(${JSON.stringify(gridSelector)}))`)),
    READINESS_TIMEOUT_MS,
  )
}

// Resolve the visible card index using the same newest-first summary ordering as the UI.
async function resolveSetCardIndex(client, recordingSetId) {
  const cardIndex = await evaluate(client, `(async () => {
    const response = await fetch('https://127.0.0.1:5000/api/sessions-info?profile=ui')
    const payload = await response.json()
    const summaries = payload?.data?.[${JSON.stringify(SESSION_ID)}]?.Recording_Set_Summaries ?? {}
    return Object.entries(summaries)
      .sort((left, right) => Date.parse(right[1]?.created_at ?? '') - Date.parse(left[1]?.created_at ?? ''))
      .findIndex(([id]) => id === ${JSON.stringify(recordingSetId)})
  })()`, true)
  if (!Number.isInteger(cardIndex) || cardIndex < 0) {
    throw new Error(`Recording set ${recordingSetId} was not found in the controlled session`)
  }
  return cardIndex
}

async function measureFirstUsable(client, cacheState) {
  await client.send('Network.setCacheDisabled', { cacheDisabled: cacheState === 'cold' })
  if (cacheState === 'cold') await client.send('Network.clearBrowserCache')
  const startedAt = performance.now()
  await navigate(client, `${OPERATOR_ORIGIN}/?benchmark=${Date.now()}`)
  await waitForUsableShell(client)
  return performance.now() - startedAt
}

async function measureRecordingNavigation(client) {
  await navigate(client, OPERATOR_ORIGIN)
  await waitForUsableShell(client)
  const startedAt = performance.now()
  const clicked = await evaluate(client, `(() => {
    const button = [...document.querySelectorAll('nav[aria-label="Primary"] button')]
      .find(item => item.textContent?.trim() === 'Recordings')
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!clicked) throw new Error('Recordings navigation button was not found')
  await waitFor(
    async () => Boolean(await evaluate(client, "Boolean(document.querySelector('main.recording-page'))")),
    READINESS_TIMEOUT_MS,
  )
  await evaluate(
    client,
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    true,
  )
  return performance.now() - startedAt
}

async function openFixtureRecordingSet(client, cacheState = 'warm', diagnosticContext = null) {
  await client.send('Network.setCacheDisabled', { cacheDisabled: cacheState === 'cold' })
  if (cacheState === 'cold') await client.send('Network.clearBrowserCache')
  await navigate(client, OPERATOR_ORIGIN)
  await waitForUsableShell(client)
  const clicked = await evaluate(client, `(() => {
    const button = [...document.querySelectorAll('nav[aria-label="Primary"] button')]
      .find(item => item.textContent?.trim() === 'Recordings')
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!clicked) throw new Error('Recordings navigation button was not found')
  await waitFor(
    async () => Boolean(await evaluate(client, "Boolean(document.querySelector('main.recording-page .recording-set-grid'))")),
    READINESS_TIMEOUT_MS,
  )
  const cardIndex = await evaluate(client, `(async () => {
    const response = await fetch('https://127.0.0.1:5000/api/sessions-info?profile=ui')
    const payload = await response.json()
    const summaries = payload?.data?.[${JSON.stringify(SESSION_ID)}]?.Recording_Set_Summaries ?? {}
    return Object.entries(summaries)
      .sort((left, right) => Date.parse(right[1]?.created_at ?? '') - Date.parse(left[1]?.created_at ?? ''))
      .findIndex(([id]) => id === ${JSON.stringify(RECORDING_SET_ID)})
  })()`, true)
  if (!Number.isInteger(cardIndex) || cardIndex < 0) {
    throw new Error(`Recording set ${RECORDING_SET_ID} was not found in the controlled session`)
  }
  await evaluate(client, 'performance.clearResourceTimings()')
  const startedAt = performance.now()
  const opened = await evaluate(client, `(() => {
    const card = document.querySelectorAll('.recording-set-card')[${cardIndex}]
    if (!card) return false
    card.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }))
    return true
  })()`)
  if (!opened) throw new Error(`Recording set card index ${cardIndex} was not rendered`)
  await waitFor(
    async () => Boolean(await evaluate(client, `(() => {
      const videos = [...document.querySelectorAll('section.recording-set-open video.recording-tile-video')]
      return videos.length === ${EXPECTED_CAMERA_COUNT} &&
        videos.every(video => video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA)
    })()`)),
    READINESS_TIMEOUT_MS,
  )
  const elapsedMs = performance.now() - startedAt
  if (diagnosticContext?.samples) {
    const resources = await evaluate(client, `performance.getEntriesByType('resource').map(entry => ({
      name: entry.name,
      initiator_type: entry.initiatorType,
      start_time_ms: entry.startTime,
      duration_ms: entry.duration,
      response_start_ms: entry.responseStart,
      response_end_ms: entry.responseEnd,
      transfer_size_bytes: entry.transferSize,
      encoded_body_size_bytes: entry.encodedBodySize,
    }))`)
    diagnosticContext.samples.push({
      run_index: diagnosticContext.index,
      elapsed_ms: elapsedMs,
      resources,
    })
  }
  return elapsedMs
}

async function measureRecordingPreviewStartup(client, cacheState, diagnosticContext) {
  return openFixtureRecordingSet(client, cacheState, diagnosticContext)
}

async function measureRecordingFirstFrame(client) {
  return evaluate(client, `new Promise((resolve, reject) => {
    const video = document.querySelector('section.recording-set-open video.recording-tile-video')
    if (!video) return reject(new Error('primary recording video is missing'))
    const startedAt = performance.now()
    const timeout = setTimeout(() => reject(new Error('first video frame timed out')), ${READINESS_TIMEOUT_MS})
    const finish = () => {
      clearTimeout(timeout)
      video.pause()
      resolve(performance.now() - startedAt)
    }
    if (typeof video.requestVideoFrameCallback === 'function') video.requestVideoFrameCallback(finish)
    else video.addEventListener('playing', finish, { once: true })
    video.play().catch(reject)
  })`, true)
}

async function measureRecordingSeekReadiness(client) {
  return evaluate(client, `new Promise((resolve, reject) => {
    const videos = [...document.querySelectorAll('section.recording-set-open video.recording-tile-video')]
    if (videos.length !== ${EXPECTED_CAMERA_COUNT}) return reject(new Error('recording videos are missing'))
    const startedAt = performance.now()
    const formatDiagnostic = ${formatRecordingSeekDiagnostic.toString()}
    const states = videos.map((video, index) => ({
      index,
      source: video.currentSrc || video.src || '',
      readyState: video.readyState,
      currentTime: video.currentTime,
      outcome: 'pending',
    }))
    const updateState = (index, outcome) => {
      const video = videos[index]
      states[index] = {
        index,
        source: video.currentSrc || video.src || '',
        readyState: video.readyState,
        currentTime: video.currentTime,
        outcome,
      }
    }
    const timeout = setTimeout(() => {
      states.forEach((state, index) => updateState(index, state.outcome === 'pending' ? 'timeout' : state.outcome))
      reject(new Error('recording seek timed out: ' + formatDiagnostic(states)))
    }, ${READINESS_TIMEOUT_MS})
    Promise.all(videos.map((video, index) => new Promise((resolveVideo, rejectVideo) => {
      video.addEventListener('seeked', () => {
        updateState(index, 'seeked')
        resolveVideo()
      }, { once: true })
      video.addEventListener('error', () => {
        updateState(index, 'error')
        rejectVideo(new Error('recording seek failed: ' + formatDiagnostic(states)))
      }, { once: true })
      video.currentTime = video.currentTime < 15 ? 20 : 10
    }))).then(() => {
      clearTimeout(timeout)
      resolve(performance.now() - startedAt)
    }, error => {
      clearTimeout(timeout)
      reject(error)
    })
  })`, true)
}

async function measureSynchronizedPlaybackStart(client) {
  return evaluate(client, `new Promise((resolve, reject) => {
    const videos = [...document.querySelectorAll('section.recording-set-open video.recording-tile-video')]
    const playButton = [...document.querySelectorAll('footer button')]
      .find(button => button.textContent?.trim() === 'Play')
    if (videos.length !== ${EXPECTED_CAMERA_COUNT} || !playButton) {
      return reject(new Error('synchronized playback controls are missing'))
    }
    const startedAt = performance.now()
    const timeout = setTimeout(() => reject(new Error('synchronized playback timed out')), ${READINESS_TIMEOUT_MS})
    const frames = videos.map(video => new Promise(resolveVideo => {
      if (typeof video.requestVideoFrameCallback === 'function') video.requestVideoFrameCallback(resolveVideo)
      else video.addEventListener('playing', resolveVideo, { once: true })
    }))
    playButton.click()
    Promise.all(frames).then(() => {
      clearTimeout(timeout)
      videos.forEach(video => video.pause())
      resolve(performance.now() - startedAt)
    }, reject)
  })`, true)
}

// Open the fixed triangulation result and measure until its WebGL canvas is usable.
async function openFixtureThreeDSet(client) {
  await navigate(client, OPERATOR_ORIGIN)
  await waitForUsableShell(client)
  await openWorkflow(client, '3D', 'main.three-d-page .calibration-set-grid')
  const cardIndex = await resolveSetCardIndex(client, RECORDING_SET_ID)
  const startedAt = performance.now()
  const opened = await evaluate(client, `(() => {
    const card = document.querySelectorAll('main.three-d-page .three-d-set-card')[${cardIndex}]
    if (!card) return false
    card.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }))
    return true
  })()`)
  if (!opened) throw new Error(`3D set card index ${cardIndex} was not rendered`)
  await waitFor(
    async () => Boolean(await evaluate(client, "Boolean(document.querySelector('main.three-d-page--detail section[aria-label=\"3D recording set\"]'))")),
    READINESS_TIMEOUT_MS,
  )
  await waitForStage(
    'triangulation run options',
    async () => Boolean(await evaluate(client, `Boolean(
      document.querySelector('#triangulation-pose-run option[value=${JSON.stringify(TRIANGULATION_RUN_ID)}]')
    )`)),
  )
  const selectedRun = await evaluate(client, `(() => {
    const select = document.querySelector('#triangulation-pose-run')
    if (!select) return null
    if (select.value !== ${JSON.stringify(TRIANGULATION_RUN_ID)}) {
      select.value = ${JSON.stringify(TRIANGULATION_RUN_ID)}
      select.dispatchEvent(new Event('change', { bubbles: true }))
    }
    return select.value
  })()`)
  if (selectedRun !== TRIANGULATION_RUN_ID) {
    throw new Error(`Triangulation run ${TRIANGULATION_RUN_ID} was not selectable`)
  }
  await waitFor(
    async () => Boolean(await evaluate(client, `(() => {
      const canvas = document.querySelector('section[aria-label="3D reconstructed viewer"] .three-d-viewer-canvas-wrap canvas')
      const label = document.querySelector('.three-d-timeline-panel .three-d-frame-label')
      if (!canvas || canvas.width <= 1 || canvas.height <= 1 || !label) return false
      const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl')
      return Boolean(context && !context.isContextLost() &&
        !document.body.textContent?.includes('Loading 3D data') &&
        label.textContent?.includes('/ ${TRIANGULATION_MAX_FRAME}'))
    })()`)),
    READINESS_TIMEOUT_MS,
  )
  await evaluate(
    client,
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    true,
  )
  return performance.now() - startedAt
}

// Seek the 3D timeline and wait until React and the renderer agree on the target frame.
async function measureThreeDSeekReadiness(client, ratio = 0.5) {
  const targetFrame = Math.round(TRIANGULATION_MAX_FRAME * ratio)
  const acceptableDelta = Math.ceil(TRIANGULATION_MAX_FRAME * 0.01)
  const point = await evaluate(client, `(() => {
    const track = document.querySelector('.three-d-timeline-panel .timeline-track[aria-label="Training timeline"]')
    if (!track) return null
    const rect = track.getBoundingClientRect()
    return { x: rect.left + rect.width * ${ratio}, y: rect.top + rect.height / 2 }
  })()`)
  if (!point) throw new Error('3D training timeline was not rendered')
  const startedAt = performance.now()
  await client.send('Input.dispatchMouseEvent', {
    type: 'mousePressed',
    x: point.x,
    y: point.y,
    button: 'left',
    clickCount: 1,
  })
  await client.send('Input.dispatchMouseEvent', {
    type: 'mouseReleased',
    x: point.x,
    y: point.y,
    button: 'left',
    clickCount: 1,
  })
  try {
    await waitFor(
      async () => Boolean(await evaluate(client, `(() => {
        const label = document.querySelector('.three-d-frame-label')?.textContent ?? ''
        const frame = Number(label.match(/Frame (\\d+)/)?.[1])
        return label.includes('/ ${TRIANGULATION_MAX_FRAME}') &&
          Number.isFinite(frame) && Math.abs(frame - ${targetFrame}) <= ${acceptableDelta}
      })()`)),
      READINESS_TIMEOUT_MS,
    )
  } catch (error) {
    const label = await evaluate(client, "document.querySelector('.three-d-frame-label')?.textContent")
    throw new Error(`3D seek target ${targetFrame} was not reached; observed ${String(label)}`)
  }
  await evaluate(
    client,
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    true,
  )
  return performance.now() - startedAt
}

// Start timeline playback and measure until a later rendered frame is reported.
async function measureThreeDPlaybackStart(client) {
  await measureThreeDSeekReadiness(client, 0.5)
  const initialFrame = await evaluate(client, `Number(
    document.querySelector('.three-d-frame-label')?.textContent?.match(/Frame (\\d+)/)?.[1]
  )`)
  const startedAt = performance.now()
  const clicked = await evaluate(client, `(() => {
    const button = document.querySelector('.three-d-timeline-panel .timeline-button')
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!clicked) throw new Error('3D timeline playback button was not rendered')
  await waitFor(async () => {
    const frame = await evaluate(client, `Number(
      document.querySelector('.three-d-frame-label')?.textContent?.match(/Frame (\\d+)/)?.[1]
    )`)
    return Number.isFinite(frame) && frame > initialFrame
  }, READINESS_TIMEOUT_MS)
  await evaluate(client, `(() => {
    const button = document.querySelector('.three-d-timeline-panel .timeline-button')
    if (button?.textContent?.trim() === 'Pause') button.click()
  })()`)
  return performance.now() - startedAt
}

// Discover the UI's viewer URL, then measure the canonical Plotly document directly.
async function measureCalibrationPlotlyReadiness(client) {
  await navigate(client, OPERATOR_ORIGIN)
  await waitForUsableShell(client)
  await openWorkflow(client, 'Calibration', 'main.calibration-page .calibration-set-grid')
  const cardIndex = await resolveSetCardIndex(client, CALIBRATION_RECORDING_SET_ID)
  const opened = await evaluate(client, `(() => {
    const card = document.querySelectorAll('main.calibration-page .calibration-set-card')[${cardIndex}]
    if (!card) return false
    card.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, detail: 2 }))
    return true
  })()`)
  if (!opened) throw new Error(`Calibration set card index ${cardIndex} was not rendered`)
  await waitForStage(
    'calibration detail',
    async () => Boolean(await evaluate(client, "Boolean(document.querySelector('section.calibration-set-open[aria-label=\"Calibration set\"]'))")),
  )
  const cameraModeSelected = await evaluate(client, `(() => {
    const button = document.querySelector('[role="radiogroup"][aria-label="Calibration preview mode"] button[aria-label="Camera view"]')
    if (!button) return false
    button.click()
    return true
  })()`)
  if (!cameraModeSelected) throw new Error('Calibration camera-view control was not rendered')
  const expectedSuffix = `/calibration-viewers/${CALIBRATION_ID}.html`
  await waitForStage(
    'calibration viewer iframe',
    async () => Boolean(await evaluate(client, `Boolean(document.querySelector('.calibration-detail-camera-iframe[src$=${JSON.stringify(expectedSuffix)}]'))`)),
  )
  const viewerUrl = await evaluate(client, `document.querySelector(
    '.calibration-detail-camera-iframe[src$=${JSON.stringify(expectedSuffix)}]'
  )?.src`)
  if (!viewerUrl) throw new Error('Calibration viewer URL was not available')
  const viewerStartedAt = performance.now()
  await navigate(client, viewerUrl)
  await waitForStage('calibration Plotly canvas', async () => Boolean(await evaluate(client, `Boolean(
    document.readyState === 'complete' &&
    document.querySelector('#root.js-plotly-plot') &&
    document.querySelector('#root .gl-container canvas')
  )`)))
  await evaluate(
    client,
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))',
    true,
  )
  return performance.now() - viewerStartedAt
}

async function captureElementIdentity(client, selector) {
  const clip = await evaluate(client, `(() => {
    const element = document.querySelector(${JSON.stringify(selector)})
    if (!element) return null
    const rect = element.getBoundingClientRect()
    return { x: rect.left, y: rect.top, width: rect.width, height: rect.height, scale: 1 }
  })()`)
  if (!clip || clip.width <= 1 || clip.height <= 1) {
    throw new Error(`Cannot capture missing element: ${selector}`)
  }
  const screenshot = await client.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    clip,
  })
  return createHash('sha256').update(Buffer.from(screenshot.data, 'base64')).digest('hex')
}

async function measureScenario(client, operation, scenarioName = 'scenario') {
  process.stderr.write(`[browser baseline] ${scenarioName}: starting\n`)
  for (let index = 0; index < WARMUP_RUNS; index += 1) {
    await operation(client, { kind: 'warmup', index })
    process.stderr.write(`[browser baseline] ${scenarioName}: warm-up ${index + 1}/${WARMUP_RUNS}\n`)
  }
  const samples = []
  for (let index = 0; index < MEASURED_RUNS; index += 1) {
    samples.push(await operation(client, { kind: 'measured', index }))
    process.stderr.write(`[browser baseline] ${scenarioName}: measured ${index + 1}/${MEASURED_RUNS}\n`)
  }
  return summarizeSamples(samples)
}

async function measureOptionalScenario(client, name, cacheState, operation) {
  try {
    return {
      result: completeResult(name, cacheState, await measureScenario(client, operation, name)),
      unavailable: null,
    }
  } catch (error) {
    return {
      result: null,
      unavailable: {
        name,
        status: 'unavailable',
        reason: error instanceof Error ? error.message : String(error),
      },
    }
  }
}

async function captureOutputIdentity(client) {
  const signature = await evaluate(client, `JSON.stringify({
    shellMode: document.querySelector('.app')?.getAttribute('data-shell-mode'),
    navigation: [...document.querySelectorAll('nav[aria-label="Primary"] button')]
      .map(item => item.textContent?.trim()),
    sessions: [...document.querySelectorAll('.tree-item.session-row .tree-label')]
      .map(item => item.textContent?.trim()),
    activeMain: document.querySelector('main')?.className,
  })`)
  return hashOperatorShellSignature(signature)
}

function completeResult(name, cacheState, summary) {
  return {
    name,
    cache_state: cacheState,
    ...summary,
    warmup_runs: WARMUP_RUNS,
    minimum_measured_runs: MEASURED_RUNS,
    minimum_warmup_runs: WARMUP_RUNS,
    maximum_p95_ms: null,
    warmup_failures: [],
    work_units: [],
    unit_name: null,
    throughput_per_second: null,
  }
}

async function run() {
  const profileDirectory = await mkdtemp(join(tmpdir(), 'mcs-browser-benchmark-'))
  const buildEnvironment = {
    ...process.env,
    VITE_EDGE_MODE: 'false',
    VITE_API_URL: 'https://127.0.0.1:5000',
  }
  await runProcess(process.execPath, [TYPESCRIPT_ENTRYPOINT, '-b'], {
    cwd: OPERATOR_ROOT,
    env: buildEnvironment,
  })
  await runProcess(process.execPath, [VITE_ENTRYPOINT, 'build'], {
    cwd: OPERATOR_ROOT,
    env: buildEnvironment,
  })
  const preview = launch(process.execPath, [VITE_ENTRYPOINT, 'preview', '--host', '127.0.0.1', '--port', String(PREVIEW_PORT)], {
    cwd: OPERATOR_ROOT,
    env: buildEnvironment,
  })
  let chrome
  let client
  try {
    await waitForHttp(OPERATOR_ORIGIN)
    const chromeArguments = [
      `--user-data-dir=${profileDirectory}`,
      `--remote-debugging-port=${DEBUG_PORT}`,
      '--ignore-certificate-errors',
      '--autoplay-policy=no-user-gesture-required',
      '--no-first-run',
      '--disable-default-apps',
      '--window-size=1440,1000',
      'about:blank',
    ]
    chrome = launch(CHROME_PATH, chromeArguments)
    client = await openCdpTarget()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Network.enable')
    await prepareOrigin(client)

    const results = [
      completeResult(
        'operator_first_usable',
        'cold',
        await measureScenario(client, (activeClient) => measureFirstUsable(activeClient, 'cold'), 'operator_first_usable_cold'),
      ),
      completeResult(
        'operator_first_usable',
        'warm',
        await measureScenario(client, (activeClient) => measureFirstUsable(activeClient, 'warm'), 'operator_first_usable_warm'),
      ),
      completeResult(
        'operator_recordings_navigation',
        'warm',
        await measureScenario(client, measureRecordingNavigation, 'operator_recordings_navigation'),
      ),
    ]
    const outputIdentity = await captureOutputIdentity(client)
    const recordingPreviewResourceSamples = []
    const optionalOutcomes = []
    optionalOutcomes.push(await measureOptionalScenario(
      client,
      'recording_preview_startup',
      'cold',
      (activeClient, context) => measureRecordingPreviewStartup(
        activeClient,
        'cold',
        context.kind === 'measured'
          ? { index: context.index, samples: recordingPreviewResourceSamples }
          : null,
      ),
    ))
    await openFixtureRecordingSet(client, 'warm')
    optionalOutcomes.push(await measureOptionalScenario(
      client,
      'recording_first_frame',
      'warm',
      measureRecordingFirstFrame,
    ))
    await openFixtureRecordingSet(client, 'warm')
    optionalOutcomes.push(await measureOptionalScenario(
      client,
      'recording_seek_readiness',
      'warm',
      measureRecordingSeekReadiness,
    ))
    await openFixtureRecordingSet(client, 'warm')
    optionalOutcomes.push(await measureOptionalScenario(
      client,
      'recording_synchronized_playback_start',
      'warm',
      measureSynchronizedPlaybackStart,
    ))
    const threeDFirstUsable = await measureOptionalScenario(
      client,
      'three_d_first_usable_render',
      'warm',
      openFixtureThreeDSet,
    )
    optionalOutcomes.push(threeDFirstUsable)
    let threeDOutputIdentity = null
    if (threeDFirstUsable.result) {
      threeDOutputIdentity = await captureElementIdentity(
        client,
        'section[aria-label="3D reconstructed viewer"] .three-d-viewer-canvas-wrap',
      )
      optionalOutcomes.push(await measureOptionalScenario(
        client,
        'three_d_timeline_seek_readiness',
        'warm',
        async (activeClient) => {
          await measureThreeDSeekReadiness(activeClient, 0.25)
          return measureThreeDSeekReadiness(activeClient, 0.5)
        },
      ))
      optionalOutcomes.push(await measureOptionalScenario(
        client,
        'three_d_playback_start',
        'warm',
        measureThreeDPlaybackStart,
      ))
    }
    const calibrationReadiness = await measureOptionalScenario(
      client,
      'calibration_plotly_readiness',
      'warm',
      measureCalibrationPlotlyReadiness,
    )
    optionalOutcomes.push(calibrationReadiness)
    let calibrationOutputIdentity = null
    if (calibrationReadiness.result) {
      calibrationOutputIdentity = await captureElementIdentity(
        client,
        '#root.js-plotly-plot',
      )
    }
    results.push(...optionalOutcomes.map(outcome => outcome.result).filter(Boolean))
    const unavailable = optionalOutcomes.map(outcome => outcome.unavailable).filter(Boolean)
    const runtimeProvenance = discoverRuntimeProvenance()
    const buildProvenance = createBuildProvenance({
      viteEdgeMode: buildEnvironment.VITE_EDGE_MODE,
      viteApiUrl: buildEnvironment.VITE_API_URL,
      previewPort: PREVIEW_PORT,
      chromeArguments: chromeArguments.map(argument => (
        argument.startsWith('--user-data-dir=')
          ? '--user-data-dir=<isolated temporary profile>'
          : argument
      )),
    })
    const payload = {
      schema_version: 1,
      created_at_utc: new Date().toISOString(),
      metadata: {
        commit: (await import('node:child_process')).execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        source_revisions: {
          laptop: (await import('node:child_process')).execFileSync('git', ['-C', 'laptop', 'rev-parse', 'HEAD'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        },
        platform: `${process.platform}-${process.arch}`,
        python: (await import('node:child_process')).execFileSync('python', ['--version'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        node: process.version,
        ...runtimeProvenance,
        network_route: 'production Vite preview http://127.0.0.1:4173 -> backend https://127.0.0.1:5000',
        database_snapshot: 'live fixture observed 2026-08-03; session 49',
        ...FIXTURE_REPORT_METADATA,
        ...buildProvenance,
        dependency_versions: { operator_lockfile: 'laptop/package-lock.json' },
        compose_configuration: '3f3fc93872540702653310569ed6a7bd5e4933151bfc6e1207db05b14e591251',
        service_images: { backend: 'sha256:55ddc0be147281760c667d996685c8b5eb3daa3efc52cdf456919c50a56320f7' },
        cache_preparation: {
          cold: 'isolated profile plus Network.clearBrowserCache and cache disabled',
          warm: 'same isolated profile with browser cache enabled after warmups',
        },
        chrome_path: CHROME_PATH,
        origin: OPERATOR_ORIGIN,
        viewport: [1440, 1000],
        session_id: SESSION_ID,
        recording_set_id: RECORDING_SET_ID,
        warmup_runs: WARMUP_RUNS,
        measured_runs: MEASURED_RUNS,
        isolated_profile: true,
        expected_output_identity: outputIdentity,
        three_d_output_identity: threeDOutputIdentity,
        calibration_output_identity: calibrationOutputIdentity,
        diagnostics: {
          recording_preview_resources: recordingPreviewResourceSamples,
        },
      },
      results,
      unavailable,
    }
    await mkdir(resolve(OUTPUT_PATH, '..'), { recursive: true })
    const temporaryPath = `${OUTPUT_PATH}.tmp`
    await writeFile(temporaryPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
    await (await import('node:fs/promises')).rename(temporaryPath, OUTPUT_PATH)
    process.stdout.write(`${OUTPUT_PATH}\n`)
  } finally {
    client?.close()
    chrome?.kill()
    preview.kill()
    await new Promise((resolveExit) => setTimeout(resolveExit, 250))
    await rm(profileDirectory, {
      recursive: true,
      force: true,
      maxRetries: 10,
      retryDelay: 100,
    }).catch(() => undefined)
  }
}

await run()
