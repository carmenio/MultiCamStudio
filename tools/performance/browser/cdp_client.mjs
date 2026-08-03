// Minimal Chrome DevTools Protocol client with deterministic command correlation.
export class CdpClient {
  constructor(socket) {
    this.socket = socket
    this.nextId = 1
    this.pending = new Map()
    this.listeners = new Map()
    socket.addEventListener('message', (event) => this.handleMessage(event.data))
    socket.addEventListener('close', () => this.rejectPending(new Error('CDP socket closed')))
    socket.addEventListener('error', () => this.rejectPending(new Error('CDP socket failed')))
  }

  // Send one protocol command and resolve only its matching response.
  send(method, params = {}) {
    const id = this.nextId++
    return new Promise((resolve, reject) => {
      this.pending.set(id, { method, resolve, reject })
      this.socket.send(JSON.stringify({ id, method, params }))
    })
  }

  // Subscribe to a protocol event and return a cleanup function.
  on(method, listener) {
    const listeners = this.listeners.get(method) ?? new Set()
    listeners.add(listener)
    this.listeners.set(method, listeners)
    return () => listeners.delete(listener)
  }

  // Decode responses and events without allowing unrelated messages to cross-talk.
  handleMessage(rawMessage) {
    const message = JSON.parse(String(rawMessage))
    if (message.id != null) {
      const pending = this.pending.get(message.id)
      if (!pending) return
      this.pending.delete(message.id)
      if (message.error) {
        pending.reject(
          new Error(`${pending.method}: ${message.error.message ?? 'CDP command failed'}`),
        )
      }
      else pending.resolve(message.result ?? {})
      return
    }
    for (const listener of this.listeners.get(message.method) ?? []) {
      listener(message.params ?? {})
    }
  }

  // Reject commands that cannot complete after transport shutdown.
  rejectPending(error) {
    for (const pending of this.pending.values()) pending.reject(error)
    this.pending.clear()
  }

  close() {
    this.socket.close()
  }
}

// Wait for a predicate with a bounded polling interval.
export async function waitFor(predicate, timeoutMs, pollMs = 25) {
  const deadline = performance.now() + timeoutMs
  while (performance.now() < deadline) {
    if (await predicate()) return
    await new Promise((resolve) => setTimeout(resolve, pollMs))
  }
  throw new Error(`readiness timed out after ${timeoutMs} ms`)
}

export function nearestRankPercentile(values, percentile) {
  if (values.length === 0) throw new Error('at least one sample is required')
  const ordered = [...values].sort((left, right) => left - right)
  const rank = Math.max(1, Math.ceil((percentile / 100) * ordered.length))
  return ordered[rank - 1]
}

export function summarizeSamples(values) {
  if (values.length === 0) throw new Error('at least one sample is required')
  const ordered = [...values].sort((left, right) => left - right)
  const middle = Math.floor(ordered.length / 2)
  const median = ordered.length % 2
    ? ordered[middle]
    : (ordered[middle - 1] + ordered[middle]) / 2
  return {
    samples_ms: values,
    successful_runs: values.length,
    measured_runs: values.length,
    failure_count: 0,
    failures: [],
    median_ms: median,
    p50_ms: median,
    p95_ms: nearestRankPercentile(values, 95),
    minimum_ms: ordered[0],
    maximum_ms: ordered.at(-1),
  }
}
