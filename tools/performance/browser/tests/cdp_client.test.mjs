import assert from 'node:assert/strict'
import test from 'node:test'

import {
  CdpClient,
  nearestRankPercentile,
  summarizeSamples,
  waitFor,
} from '../cdp_client.mjs'

class FakeSocket {
  constructor() {
    this.listeners = new Map()
    this.sent = []
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? []
    listeners.push(listener)
    this.listeners.set(type, listeners)
  }

  send(message) {
    this.sent.push(JSON.parse(message))
  }

  emit(type, value = {}) {
    for (const listener of this.listeners.get(type) ?? []) listener(value)
  }

  close() {
    this.emit('close')
  }
}

test('CDP responses resolve only their matching command', async () => {
  const socket = new FakeSocket()
  const client = new CdpClient(socket)
  const first = client.send('Page.enable')
  const second = client.send('Runtime.enable')
  socket.emit('message', { data: JSON.stringify({ id: 2, result: { second: true } }) })
  socket.emit('message', { data: JSON.stringify({ id: 1, result: { first: true } }) })
  assert.deepEqual(await first, { first: true })
  assert.deepEqual(await second, { second: true })
})

test('CDP errors reject the matching command', async () => {
  const socket = new FakeSocket()
  const client = new CdpClient(socket)
  const pending = client.send('Page.navigate')
  socket.emit('message', { data: JSON.stringify({ id: 1, error: { message: 'bad target' } }) })
  await assert.rejects(pending, /bad target/)
})

test('readiness polling times out with a stable diagnostic', async () => {
  await assert.rejects(waitFor(() => false, 5, 1), /readiness timed out after 5 ms/)
})

test('statistics use median and nearest-rank p95', () => {
  const samples = [1, 2, 3, 4, 5, 6, 7, 8, 9, 20]
  assert.equal(nearestRankPercentile(samples, 95), 20)
  assert.deepEqual(summarizeSamples(samples), {
    samples_ms: samples,
    successful_runs: 10,
    measured_runs: 10,
    failure_count: 0,
    failures: [],
    median_ms: 5.5,
    p50_ms: 5.5,
    p95_ms: 20,
    minimum_ms: 1,
    maximum_ms: 20,
  })
})

test('socket shutdown rejects every outstanding command', async () => {
  const socket = new FakeSocket()
  const client = new CdpClient(socket)
  const first = client.send('Page.enable')
  const second = client.send('Runtime.enable')
  socket.close()
  await assert.rejects(first, /CDP socket closed/)
  await assert.rejects(second, /CDP socket closed/)
})
