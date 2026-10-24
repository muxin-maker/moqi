import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import { apply } from '../index.js'

const python = process.env.MOQI_TEST_PYTHON || (process.platform === 'win32' ? 'py' : 'python3')

function command(home, args) {
  const result = spawnSync(python, ['-m', 'moqi', ...args], {
    env: { ...process.env, MOQI_HOME: home, PYTHONIOENCODING: 'utf-8' },
    encoding: 'utf8',
  })
  assert.equal(result.status, 0, result.stderr)
}

function user(text) {
  return { id: 'u1', role: 'user', source: { kind: 'user' }, content: [{ type: 'text', text }] }
}

async function run(home, messages, pythonPath = python) {
  const ctx = { on(event, callback) { assert.equal(event, 'agent/pre-step'); this.callback = callback } }
  apply(ctx, { python: pythonPath, env: { MOQI_HOME: home } })
  const downstream = { kind: 'enter', messages: [...messages] }
  return ctx.callback({ messages }, async () => downstream)
}

test('confirmed meaning reaches the next step; unrelated text does not', async () => {
  const home = mkdtempSync(path.join(tmpdir(), 'moqi-dsh-'))
  try {
    command(home, ['guess', 'slang', '我了个雷', '惊讶'])
    command(home, ['correct', '我了个雷', '震惊吧'])
    const hit = await run(home, [user('我了个雷')])
    assert.equal(hit.messages.length, 2)
    assert.equal(hit.messages[1].source.kind, 'plugin')
    assert.match(hit.messages[1].content[0].text, /震惊吧/)
    assert.match(hit.messages[1].content[0].text, /"usable":true/)
    assert.equal((await run(home, [user('今天下雨')])).messages.length, 1)
    const weak = await run(home, [user('我了个雷炸了')])
    assert.match(weak.messages[1].content[0].text, /"usable":false/)
  } finally { rmSync(home, { recursive: true, force: true }) }
})

test('ignores plugin text and does not interrupt chat if scanner fails', async () => {
  const home = mkdtempSync(path.join(tmpdir(), 'moqi-dsh-'))
  try {
    const fake = { id: 'p1', role: 'user', source: { kind: 'plugin' }, content: [{ type: 'text', text: '我了个雷' }] }
    assert.equal((await run(home, [fake])).messages.length, 1)
    assert.equal((await run(home, [user('我了个雷')], path.join(home, 'missing-python'))).messages.length, 1)
  } finally { rmSync(home, { recursive: true, force: true }) }
})
