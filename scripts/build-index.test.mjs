// node --test scripts/
import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { build } from './build-index.mjs'

const skill = (root, name, front, extra = {}) => {
  const dir = join(root, 'skills', name)
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'SKILL.md'), `---\n${front}\n---\nBody\n`)
  for (const [file, body] of Object.entries(extra)) {
    mkdirSync(join(dir, file, '..'), { recursive: true })
    writeFileSync(join(dir, file), body)
  }
}

test('valid skill is indexed with metadata and script flag', () => {
  const root = mkdtempSync(join(tmpdir(), 'skills-'))
  skill(root, 'good', 'name: good\ndescription: >\n  Does a\n  thing.\nlicense: MIT\nmetadata:\n  category: dev\n  author: zero1', { 'scripts/run.sh': 'echo' })
  const { errors, text } = build(root)
  assert.deepEqual(errors, [])
  const [entry] = JSON.parse(text).skills
  assert.equal(entry.description, 'Does a thing.')
  assert.equal(entry.category, 'dev')
  assert.equal(entry.hasScripts, true)
  assert.deepEqual(entry.files.map((f) => f.path), ['SKILL.md', 'scripts/run.sh'])
})

test('name mismatch, missing description and license are all reported', () => {
  const root = mkdtempSync(join(tmpdir(), 'skills-'))
  skill(root, 'bad', 'name: other')
  const { errors } = build(root)
  assert.equal(errors.length, 3)
})
