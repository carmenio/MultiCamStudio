// Benchmark the production signaling relay without requiring physical devices or WebRTC media.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync, spawn } from 'node:child_process'
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import net from 'node:net'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve, sep } from 'node:path'
import { performance } from 'node:perf_hooks'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const REPOSITORY_ROOT = resolve(import.meta.dirname, '..', '..')
const SIGNALING_ROOT = join(REPOSITORY_ROOT, 'laptop', 'services', 'signaling')
const SIGNALING_SERVER = join(SIGNALING_ROOT, 'server.js')
const OUTPUT_PATH = join(
  REPOSITORY_ROOT,
  'tools',
  'performance',
  'results',
  'phase_00_signaling',
  'phase_00_signaling_baseline.json',
)
const WARMUP_RUNS = 3
const MEASURED_RUNS = 10
const OPERATION_TIMEOUT_MS = 8_000
const TEMP_PREFIX = 'multicam-signaling-benchmark-'
const ROOM_ID = 'phase-00-signaling-room'
const DEVICE_ID = 'phase-00-camera'
const HARDWARE = '11th Gen Intel(R) Core(TM) i9-11900K @ 3.50GHz; 68595343360 bytes RAM'
const POWER_MODE = 'Balanced'

// Mirror the universal report comparison contract for this Node-owned runner.
export const COMPARISON_METADATA_KEYS = Object.freeze([
  'platform',
  'python',
  'node',
  'hardware',
  'power_mode',
  'network_route',
  'database_snapshot',
  'fixture',
  'build_mode',
  'dependency_versions',
  'compose_configuration',
  'service_images',
  'cache_preparation',
  'camera_count',
  'recording_duration_seconds',
  'media_sizes_bytes',
  'expected_output_identity',
])

const requireFromSignaling = createRequire(join(SIGNALING_ROOT, 'package.json'))
const { WebSocket } = requireFromSignaling('ws')
const { version: WS_VERSION } = requireFromSignaling('ws/package.json')

// Return percentile values using the nearest-rank convention used by the other baseline runners.
export function summarizeSamples(samples) {
  assert.ok(samples.length > 0, 'At least one measured sample is required')
  const sorted = [...samples].sort((left, right) => left - right)
  const medianIndex = Math.floor(sorted.length / 2)
  const median = sorted.length % 2
    ? sorted[medianIndex]
    : (sorted[medianIndex - 1] + sorted[medianIndex]) / 2
  const p95Index = Math.max(0, Math.ceil(sorted.length * 0.95) - 1)
  return {
    samples_ms: samples.map(roundMilliseconds),
    successful_runs: samples.length,
    measured_runs: samples.length,
    failure_count: 0,
    failures: [],
    median_ms: roundMilliseconds(median),
    p50_ms: roundMilliseconds(median),
    p95_ms: roundMilliseconds(sorted[p95Index]),
    minimum_ms: roundMilliseconds(sorted[0]),
    maximum_ms: roundMilliseconds(sorted.at(-1)),
  }
}

function roundMilliseconds(value) {
  return Math.round(value * 1_000) / 1_000
}

// Sort object keys recursively so equivalent relayed messages have a stable identity.
export function stableStringify(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`
  }
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(',')}}`
  }
  return JSON.stringify(value)
}

// Remove the unique waiter token before hashing otherwise-identical protocol messages.
export function normalizedMessageIdentity(message) {
  const normalized = { ...message, benchmarkCorrelationId: '<correlation-id>' }
  return createHash('sha256').update(stableStringify(normalized)).digest('hex')
}

function getFreePort() {
  return new Promise((resolvePort, rejectPort) => {
    const probe = net.createServer()
    probe.once('error', rejectPort)
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address()
      probe.close((error) => {
        if (error) rejectPort(error)
        else if (address && typeof address === 'object') resolvePort(address.port)
        else rejectPort(new Error('Could not resolve a free signaling port'))
      })
    })
  })
}

function boundedLogAppend(current, chunk) {
  return `${current}${chunk.toString()}`.slice(-65_536)
}

async function startProductionServer(temporaryRoot) {
  const port = await getFreePort()
  const recordingsPath = join(temporaryRoot, 'recordings')
  const child = spawn(process.execPath, [SIGNALING_SERVER], {
    cwd: SIGNALING_ROOT,
    env: {
      ...process.env,
      PORT: String(port),
      SIGNAL_CERT_PATH: join(temporaryRoot, 'missing-cert.pem'),
      SIGNAL_KEY_PATH: join(temporaryRoot, 'missing-key.pem'),
      SIGNAL_RECORDINGS_PATH: recordingsPath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })

  let stdout = ''
  let stderr = ''
  child.stdout.on('data', (chunk) => { stdout = boundedLogAppend(stdout, chunk) })
  child.stderr.on('data', (chunk) => { stderr = boundedLogAppend(stderr, chunk) })

  await new Promise((resolveStart, rejectStart) => {
    const timeout = setTimeout(() => {
      rejectStart(new Error(`Signaling startup timed out. stdout=${stdout} stderr=${stderr}`))
    }, OPERATION_TIMEOUT_MS)
    const onData = (chunk) => {
      if (!chunk.toString().includes(`ws://localhost:${port}`)) return
      clearTimeout(timeout)
      child.stdout.off('data', onData)
      resolveStart()
    }
    child.stdout.on('data', onData)
    child.once('error', (error) => {
      clearTimeout(timeout)
      rejectStart(error)
    })
    child.once('exit', (code) => {
      clearTimeout(timeout)
      rejectStart(new Error(`Signaling server exited early (${code}). stderr=${stderr}`))
    })
  })

  return { child, port, logs: () => ({ stdout, stderr }) }
}

async function stopProductionServer(server) {
  if (!server?.child || server.child.exitCode !== null) return
  const exited = new Promise((resolveExit) => server.child.once('exit', resolveExit))
  server.child.kill('SIGTERM')
  const graceful = await Promise.race([
    exited.then(() => true),
    new Promise((resolveTimeout) => setTimeout(() => resolveTimeout(false), 2_000)),
  ])
  if (!graceful && server.child.exitCode === null) {
    server.child.kill('SIGKILL')
    await exited
  }
}

function openSocket(url) {
  return new Promise((resolveSocket, rejectSocket) => {
    const socket = new WebSocket(url)
    const timeout = setTimeout(() => {
      socket.terminate()
      rejectSocket(new Error(`WebSocket open timed out: ${url}`))
    }, OPERATION_TIMEOUT_MS)
    socket.once('open', () => {
      clearTimeout(timeout)
      resolveSocket(socket)
    })
    socket.once('error', (error) => {
      clearTimeout(timeout)
      rejectSocket(error)
    })
  })
}

function closeSocket(socket) {
  if (!socket || socket.readyState === WebSocket.CLOSED) return Promise.resolve()
  return new Promise((resolveClose) => {
    const timeout = setTimeout(() => {
      socket.terminate()
      resolveClose()
    }, 1_000)
    socket.once('close', () => {
      clearTimeout(timeout)
      resolveClose()
    })
    socket.close()
  })
}

// Each waiter is registered before its send and matched by a unique correlation token.
class CorrelatedMessageInbox {
  constructor(socket) {
    this.socket = socket
  }

  waitFor(correlationId) {
    return new Promise((resolveMessage, rejectMessage) => {
      const timeout = setTimeout(() => {
        this.socket.off('message', onMessage)
        rejectMessage(new Error(`Timed out waiting for signaling message ${correlationId}`))
      }, OPERATION_TIMEOUT_MS)
      const onMessage = (payload) => {
        let message
        try {
          message = JSON.parse(payload.toString())
        } catch {
          return
        }
        if (message.benchmarkCorrelationId !== correlationId) return
        clearTimeout(timeout)
        this.socket.off('message', onMessage)
        resolveMessage(message)
      }
      this.socket.on('message', onMessage)
    })
  }
}

function send(socket, message) {
  socket.send(JSON.stringify(message))
}

function assertExactMessage(actual, expected) {
  assert.deepEqual(actual, expected)
  return normalizedMessageIdentity(actual)
}

async function connectParticipant(url, role) {
  const socket = await openSocket(url)
  send(socket, { type: 'join', roomId: ROOM_ID, role })
  return socket
}

function correlationId(scenario, sequence) {
  return `${scenario}-${sequence}`
}

async function runTimedScenario({ name, warmupRuns, measuredRuns, execute }) {
  const samples = []
  for (let index = 0; index < warmupRuns + measuredRuns; index += 1) {
    const isWarmup = index < warmupRuns
    process.stderr.write(
      `[signaling] ${name} ${isWarmup ? 'warmup' : 'measured'} ${isWarmup ? index + 1 : index - warmupRuns + 1}/${isWarmup ? warmupRuns : measuredRuns}\n`,
    )
    const elapsed = await execute(index)
    if (!isWarmup) samples.push(elapsed)
  }
  return summarizeSamples(samples)
}

function rememberIdentity(identities, name, identity) {
  if (!identities.has(name)) identities.set(name, new Set())
  identities.get(name).add(identity)
}

function completeResult(name, summary, unitName, warmupRuns, measuredRuns) {
  const totalMilliseconds = summary.samples_ms.reduce((total, sample) => total + sample, 0)
  return {
    name,
    cache_state: 'warm',
    ...summary,
    warmup_runs: warmupRuns,
    minimum_measured_runs: measuredRuns,
    minimum_warmup_runs: warmupRuns,
    maximum_p95_ms: null,
    warmup_failures: [],
    work_units: summary.samples_ms.map(() => 1),
    unit_name: unitName,
    throughput_per_second: totalMilliseconds > 0
      ? (summary.samples_ms.length * 1_000) / totalMilliseconds
      : null,
  }
}

function assertCompleteComparisonMetadata(metadata) {
  const missingKeys = COMPARISON_METADATA_KEYS.filter((key) => !(key in metadata))
  assert.deepEqual(missingKeys, [], `Missing universal comparison metadata: ${missingKeys.join(', ')}`)
}

// Run all three lower-bound relay scenarios against one real production server process.
export async function runSignalingBenchmark({
  warmupRuns = WARMUP_RUNS,
  measuredRuns = MEASURED_RUNS,
  writeResult = true,
  outputPath = OUTPUT_PATH,
} = {}) {
  assert.ok(Number.isInteger(warmupRuns) && warmupRuns >= 0)
  assert.ok(Number.isInteger(measuredRuns) && measuredRuns > 0)
  const temporaryRoot = await mkdtemp(join(tmpdir(), TEMP_PREFIX))
  const sockets = new Set()
  const identities = new Map()
  let server

  try {
    server = await startProductionServer(temporaryRoot)
    const url = `ws://127.0.0.1:${server.port}`
    const sender = await connectParticipant(url, 'sender')
    sockets.add(sender)
    const senderInbox = new CorrelatedMessageInbox(sender)

    const connectionToViewerReady = await runTimedScenario({
      name: 'receiver connection to viewer-ready relay',
      warmupRuns,
      measuredRuns,
      execute: async (sequence) => {
        const token = correlationId('viewer-ready', sequence)
        const pending = senderInbox.waitFor(token)
        const startedAt = performance.now()
        const receiver = await connectParticipant(url, 'viewer')
        sockets.add(receiver)
        send(receiver, { type: 'viewer-ready', roomId: ROOM_ID, benchmarkCorrelationId: token })
        const relayed = await pending
        const elapsed = performance.now() - startedAt
        rememberIdentity(identities, 'viewer_ready', assertExactMessage(relayed, {
          type: 'viewer-ready',
          roomId: ROOM_ID,
          benchmarkCorrelationId: token,
          protocolVersion: 2,
        }))
        await closeSocket(receiver)
        sockets.delete(receiver)
        return elapsed
      },
    })

    const viewer = await connectParticipant(url, 'viewer')
    sockets.add(viewer)
    const viewerInbox = new CorrelatedMessageInbox(viewer)

    const canonicalRoundTrip = await runTimedScenario({
      name: 'canonical device hello/status round trip',
      warmupRuns,
      measuredRuns,
      execute: async (sequence) => {
        const token = correlationId('canonical', sequence)
        const senderRequest = senderInbox.waitFor(token)
        const viewerResponse = viewerInbox.waitFor(token)
        const startedAt = performance.now()
        send(viewer, {
          type: 'device.hello',
          roomId: ROOM_ID,
          deviceId: DEVICE_ID,
          benchmarkCorrelationId: token,
        })
        const request = await senderRequest
        rememberIdentity(identities, 'canonical_device_hello', assertExactMessage(request, {
          type: 'device.hello', roomId: ROOM_ID, deviceId: DEVICE_ID,
          benchmarkCorrelationId: token, protocolVersion: 2,
        }))
        send(sender, {
          type: 'device.status', roomId: ROOM_ID, deviceId: DEVICE_ID,
          state: 'ready', benchmarkCorrelationId: token,
        })
        const response = await viewerResponse
        const elapsed = performance.now() - startedAt
        rememberIdentity(identities, 'canonical_device_status', assertExactMessage(response, {
          type: 'device.status', roomId: ROOM_ID, deviceId: DEVICE_ID,
          state: 'ready', benchmarkCorrelationId: token, protocolVersion: 2,
        }))
        return elapsed
      },
    })

    const legacyRoundTrip = await runTimedScenario({
      name: 'legacy device-info round trip',
      warmupRuns,
      measuredRuns,
      execute: async (sequence) => {
        const token = correlationId('legacy', sequence)
        const senderRequest = senderInbox.waitFor(token)
        const viewerResponse = viewerInbox.waitFor(token)
        const startedAt = performance.now()
        send(viewer, {
          type: 'control', action: 'request-device-info', roomId: ROOM_ID,
          benchmarkCorrelationId: token,
        })
        const request = await senderRequest
        rememberIdentity(identities, 'legacy_request_device_info', assertExactMessage(request, {
          type: 'control', action: 'request-device-info', roomId: ROOM_ID,
          benchmarkCorrelationId: token, canonicalType: 'device.hello', protocolVersion: 2,
        }))
        send(sender, {
          type: 'device-info', roomId: ROOM_ID, deviceId: DEVICE_ID,
          state: 'ready', benchmarkCorrelationId: token,
        })
        const response = await viewerResponse
        const elapsed = performance.now() - startedAt
        rememberIdentity(identities, 'legacy_device_info', assertExactMessage(response, {
          type: 'device-info', roomId: ROOM_ID, deviceId: DEVICE_ID,
          state: 'ready', benchmarkCorrelationId: token, protocolVersion: 2,
        }))
        return elapsed
      },
    })

    for (const [name, values] of identities) {
      assert.equal(values.size, 1, `${name} normalization changed between samples`)
    }
    const result = {
      schema_version: 1,
      created_at_utc: new Date().toISOString(),
      metadata: {
        commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        source_revisions: {
          laptop: execFileSync('git', ['-C', 'laptop', 'rev-parse', 'HEAD'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        },
        platform: `${process.platform}-${process.arch}`,
        python: execFileSync('python', ['--version'], { cwd: REPOSITORY_ROOT, encoding: 'utf8' }).trim(),
        node: process.version,
        dependency_versions: { ws: WS_VERSION },
        hardware: HARDWARE,
        power_mode: POWER_MODE,
        network_route: 'unencrypted loopback WebSocket to one production relay process',
        database_snapshot: 'none',
        build_mode: 'production Node entrypoint; no transpilation',
        compose_configuration: 'laptop/docker-compose.yml signaling route semantics; isolated local source process',
        service_images: { signaling: 'local source; no container' },
        cache_preparation: 'one warm server process and three warmups per scenario',
        fixture: { room_id: ROOM_ID, device_id: DEVICE_ID },
        camera_count: 1,
        recording_duration_seconds: 0,
        media_sizes_bytes: [],
        expected_output_identity: Object.fromEntries(
          [...identities].map(([name, values]) => [name, [...values][0]]),
        ),
        evidence_scope: 'Warm loopback signaling-relay lower bound only; excludes physical devices, network routing, WebRTC negotiation, media readiness, and camera behavior.',
        server_entrypoint: 'laptop/services/signaling/server.js',
        transport: 'unencrypted loopback WebSocket using deliberately nonexistent certificate paths',
        warmup_runs: warmupRuns,
        measured_runs: measuredRuns,
      },
      results: [
        completeResult('signaling_receiver_connection_to_viewer_ready', connectionToViewerReady, 'connections_ready', warmupRuns, measuredRuns),
        completeResult('signaling_canonical_control_round_trip', canonicalRoundTrip, 'round_trips', warmupRuns, measuredRuns),
        completeResult('signaling_legacy_control_round_trip', legacyRoundTrip, 'round_trips', warmupRuns, measuredRuns),
      ],
      unavailable: [],
    }
    assertCompleteComparisonMetadata(result.metadata)
    if (writeResult) {
      await mkdir(dirname(outputPath), { recursive: true })
      await writeFile(outputPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8')
      process.stderr.write(`[signaling] wrote ${outputPath}\n`)
    }
    return result
  } catch (error) {
    const logs = server?.logs()
    if (logs) {
      process.stderr.write(`[signaling] server stdout:\n${logs.stdout}\n`)
      process.stderr.write(`[signaling] server stderr:\n${logs.stderr}\n`)
    }
    throw error
  } finally {
    await Promise.allSettled([...sockets].map(closeSocket))
    await stopProductionServer(server)
    const resolvedTemporaryRoot = resolve(temporaryRoot)
    const resolvedTempDirectory = `${resolve(tmpdir())}${sep}`
    assert.ok(
      resolvedTemporaryRoot.startsWith(resolvedTempDirectory) &&
        basename(resolvedTemporaryRoot).startsWith(TEMP_PREFIX),
      `Refusing to clean an unowned path: ${resolvedTemporaryRoot}`,
    )
    await rm(resolvedTemporaryRoot, { recursive: true, force: true })
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : ''
if (invokedPath === import.meta.url) {
  runSignalingBenchmark()
    .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack || error}\n`)
      process.exitCode = 1
    })
}
