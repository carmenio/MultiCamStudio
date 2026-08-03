// Production-build browser benchmark for shell readiness and workflow navigation.
import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { performance } from 'node:perf_hooks'

import { CdpClient, summarizeSamples, waitFor } from './cdp_client.mjs'

const REPOSITORY_ROOT = resolve(import.meta.dirname, '..', '..', '..')
const OPERATOR_ROOT = join(REPOSITORY_ROOT, 'laptop', 'apps', 'operator-web')
const VITE_ENTRYPOINT = join(OPERATOR_ROOT, 'node_modules', 'vite', 'bin', 'vite.js')
const TYPESCRIPT_ENTRYPOINT = join(OPERATOR_ROOT, 'node_modules', 'typescript', 'bin', 'tsc')
const OPERATOR_ORIGIN = 'http://127.0.0.1:4173'
const PREVIEW_PORT = 4173
const DEBUG_PORT = 9223
const SESSION_ID = '49'
const WARMUP_RUNS = 3
const MEASURED_RUNS = 10
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
  if (result.exceptionDetails) throw new Error('browser expression failed')
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

async function measureScenario(client, operation) {
  for (let index = 0; index < WARMUP_RUNS; index += 1) await operation(client)
  const samples = []
  for (let index = 0; index < MEASURED_RUNS; index += 1) samples.push(await operation(client))
  return summarizeSamples(samples)
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
  return createHash('sha256').update(String(signature)).digest('hex')
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
    chrome = launch(CHROME_PATH, [
      `--user-data-dir=${profileDirectory}`,
      `--remote-debugging-port=${DEBUG_PORT}`,
      '--ignore-certificate-errors',
      '--no-first-run',
      '--disable-default-apps',
      '--window-size=1440,1000',
      'about:blank',
    ])
    client = await openCdpTarget()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Network.enable')
    await prepareOrigin(client)

    const results = [
      completeResult(
        'operator_first_usable',
        'cold',
        await measureScenario(client, (activeClient) => measureFirstUsable(activeClient, 'cold')),
      ),
      completeResult(
        'operator_first_usable',
        'warm',
        await measureScenario(client, (activeClient) => measureFirstUsable(activeClient, 'warm')),
      ),
      completeResult(
        'operator_recordings_navigation',
        'warm',
        await measureScenario(client, measureRecordingNavigation),
      ),
    ]
    const outputIdentity = await captureOutputIdentity(client)
    const unavailable = [
      'recording_preview_startup',
      'recording_first_frame',
      'recording_seek_readiness',
      'recording_synchronization',
      'three_d_first_usable_render',
    ].map((name) => ({
      name,
      status: 'unavailable',
      reason: 'requires an explicitly configured visible card/media/result fixture',
    }))
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
        hardware: '11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM',
        power_mode: 'Balanced',
        network_route: 'production Vite preview http://127.0.0.1:4173 -> backend https://127.0.0.1:5000',
        database_snapshot: 'live fixture observed 2026-08-03; session 49',
        fixture: { session_id: 49 },
        build_mode: 'Vite production build served by vite preview; headed Chrome with GPU enabled',
        dependency_versions: { operator_lockfile: 'laptop/package-lock.json' },
        compose_configuration: '3f3fc93872540702653310569ed6a7bd5e4933151bfc6e1207db05b14e591251',
        service_images: { backend: 'sha256:55ddc0be147281760c667d996685c8b5eb3daa3efc52cdf456919c50a56320f7' },
        cache_preparation: {
          cold: 'isolated profile plus Network.clearBrowserCache and cache disabled',
          warm: 'same isolated profile with browser cache enabled after warmups',
        },
        camera_count: 3,
        recording_duration_seconds: [196.1, 195.8, 195.766666666667],
        media_sizes_bytes: [450821959, 445290517, 448855126],
        chrome_path: CHROME_PATH,
        origin: OPERATOR_ORIGIN,
        viewport: [1440, 1000],
        session_id: SESSION_ID,
        warmup_runs: WARMUP_RUNS,
        measured_runs: MEASURED_RUNS,
        isolated_profile: true,
        expected_output_identity: outputIdentity,
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
